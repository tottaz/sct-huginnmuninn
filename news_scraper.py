"""Publisher-independent discovery and extraction of publicly accessible news.

Feeds are preferred; semantic HTML is the fallback. No browser automation,
subscription credentials, paywall removal, or restricted structured article bodies.
"""
from dataclasses import dataclass, asdict
import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

USER_AGENT = 'HuginnMuninn/1.0'
MAX_BYTES = 4 * 1024 * 1024
ARTICLE_TYPES = {'Article', 'NewsArticle', 'ReportageNewsArticle', 'AnalysisNewsArticle', 'BlogPosting'}
PAYWALL_TEXT = re.compile(r'(subscribe to (?:continue|read|unlock)|sign in to (?:read|continue)|subscription required|this (?:article|content) is (?:for|available to) subscribers|prenumerera för att läsa|logga in för att läsa|endast för prenumeranter)', re.I)
GATE_TEXT = re.compile(r'(enable javascript|verify (?:that )?you are human|access denied|checking your browser|accept cookies to continue)', re.I)
BOILERPLATE = re.compile(r'(cookie|consent|newsletter|related|recommended|advert|social|share|comment|navigation|footer|sidebar)', re.I)
SKIP_PATH = re.compile(r'/(?:tag|tags|category|author|authors|search|login|subscribe|account|contact|about|privacy|terms)(?:/|$)', re.I)


@dataclass
class Article:
    url: str
    title: str = ''
    lead: str = ''
    text: str = ''
    status: str = 'unavailable'
    reason: str = ''
    language: str = ''

    def to_dict(self):
        return asdict(self)


def clean(value):
    return re.sub(r'\s+', ' ', value or '').strip()


def normalized_url(href, base):
    if not href or not href.strip() or href.startswith('#'):
        return None
    parsed = urlsplit(urljoin(base, href.strip()))
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        return None
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
             if not key.lower().startswith('utm_') and key.lower() not in ('fbclid', 'gclid')]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or '/', urlencode(query), ''))


def same_site(left, right):
    return (urlsplit(left).hostname or '').removeprefix('www.') == (urlsplit(right).hostname or '').removeprefix('www.')


def unique_links(values, base, same_domain=True):
    result = []
    for href in values:
        url = normalized_url(href, base)
        if url and (not same_domain or same_site(url, base)) and url not in result:
            result.append(url)
    return result


def json_objects(soup):
    def walk(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            yield from walk(json.loads(script.string or script.get_text()))
        except (ValueError, RecursionError):
            continue


def article_metadata(soup):
    for value in json_objects(soup):
        kinds = value.get('@type', [])
        kinds = kinds if isinstance(kinds, list) else [kinds]
        if any(isinstance(kind, str) and kind.rsplit('/', 1)[-1] in ARTICLE_TYPES for kind in kinds):
            return value
    return {}


def meta(soup, *names):
    for name in names:
        element = soup.find('meta', attrs={'property': name}) or soup.find('meta', attrs={'name': name})
        if element and element.get('content'):
            return clean(element['content'])
    return ''


def parse_feed(document, base):
    """Return article links in RSS/Atom order; never use feed body as a paywall fallback."""
    try:
        root = ET.fromstring(document)
    except ET.ParseError:
        return None
    local = lambda element: element.tag.rsplit('}', 1)[-1].lower()
    if local(root) not in ('rss', 'feed', 'rdf'):
        return None
    links = []
    for item in root.iter():
        if local(item) not in ('item', 'entry'):
            continue
        for child in item:
            if local(child) == 'link' and child.get('rel', 'alternate') == 'alternate':
                candidate = child.get('href') or child.text
                if candidate:
                    links.append(candidate)
                    break
    return unique_links(links, base, same_domain=False)


def html_article_links(soup, base, selector=None):
    if selector:
        return unique_links([anchor.get('href') for anchor in soup.select(selector)], base)
    ranked = []
    for order, anchor in enumerate(soup.select('a[href]')):
        href = normalized_url(anchor['href'], base)
        if not href or not same_site(href, base) or href == normalized_url(base, base):
            continue
        path = urlsplit(href).path
        if SKIP_PATH.search(path) or path.endswith(('.jpg', '.png', '.pdf', '.mp4', '.xml')):
            continue
        if anchor.find_parent(['nav', 'footer', 'header', 'aside']):
            continue
        title = clean(anchor.get_text(' ', strip=True))
        score = 0
        if anchor.find(['h1', 'h2', 'h3']) or anchor.find_parent(['h1', 'h2', 'h3']):
            score += 5
        if anchor.find_parent('article'):
            score += 4
        if len(title.split()) >= 4:
            score += 2
        if re.search(r'\d{4}/\d{2}/\d{2}|\d{5,}|[\w]+(?:-[\w]+){3,}', path):
            score += 2
        if score >= 4:
            ranked.append((-score, order, href))
    return list(dict.fromkeys(url for _, _, url in sorted(ranked)))


def detect_restriction(soup):
    for value in json_objects(soup):
        accessible = value.get('isAccessibleForFree')
        if accessible is False or (isinstance(accessible, str) and accessible.lower() == 'false'):
            return 'Publisher marks this content as subscription-only.'
    for element in soup.select('[itemprop="isAccessibleForFree"]'):
        if str(element.get('content', element.get_text())).lower().strip() == 'false':
            return 'Publisher marks this content as subscription-only.'
    visible = BeautifulSoup(str(soup), 'html.parser')
    for element in visible.select('script, style, nav, footer, aside, [hidden], [aria-hidden="true"]'):
        element.decompose()
    # A banner mentioning subscriptions is not necessarily a blocked article.
    for element in visible.find_all(True):
        marker = ' '.join([str(element.get('id', '')), ' '.join(element.get('class', []))])
        if re.search(r'(?:^|[\s_-])(?:paywall|subscription-wall|registration-wall)(?:$|[\s_-])', marker, re.I):
            return 'A subscription or registration wall was detected.'
    text = clean(visible.get_text(' ', strip=True))
    if PAYWALL_TEXT.search(text):
        return 'The visible page requests a subscription or sign-in to read.'
    return ''


def extract_article(document, url):
    soup = BeautifulSoup(document, 'html.parser')
    metadata = article_metadata(soup)
    heading = soup.find('h1')
    title = meta(soup, 'og:title', 'twitter:title') or (clean(heading.get_text(' ', strip=True)) if heading else '')
    title = title or clean(metadata.get('headline') if isinstance(metadata.get('headline'), str) else '')
    if not title and soup.title:
        title = clean(soup.title.get_text(' ', strip=True))
    language = str(soup.html.get('lang', '')) if soup.html else ''
    result = Article(url=url, title=title, language=language)
    reason = detect_restriction(soup)
    if reason:
        result.status, result.reason = 'paywalled', reason
        return result
    description = meta(soup, 'og:description', 'description', 'twitter:description')
    for element in soup.select('script, style, noscript, nav, header, footer, aside, form, [hidden], [aria-hidden="true"]'):
        element.decompose()
    for element in list(soup.find_all(True)):
        if element.attrs is None:
            continue
        marker = ' '.join([str(element.get('id', '')), ' '.join(element.get('class', []))])
        if BOILERPLATE.search(marker):
            element.decompose()
    candidates = soup.select('[itemprop="articleBody"], article, main, [role="main"]')
    if not candidates:
        candidates = soup.find_all(['section', 'div'])
    # Link-heavy blocks are usually navigation or recommendations.
    def paragraphs(element):
        output = []
        for paragraph in element.find_all('p'):
            text = clean(paragraph.get_text(' ', strip=True))
            linked = sum(len(a.get_text(' ', strip=True)) for a in paragraph.find_all('a'))
            if len(text) >= 35 and linked < len(text) * 0.5 and text not in output:
                output.append(text)
        return output
    best = []
    best_score = 0
    for element in candidates:
        parts = paragraphs(element)
        score = sum(map(len, parts))
        if element.name == 'article' or element.get('itemprop') == 'articleBody':
            score *= 1.5
        if score > best_score:
            best, best_score = parts, score
    result.text = '\n\n'.join(best)
    result.lead = best[0] if best else description
    page_text = clean(soup.get_text(' ', strip=True))
    if GATE_TEXT.search(page_text) and len(result.text.split()) < 100:
        result.text = ''
        result.lead = ''
        result.status, result.reason = 'blocked', 'The page requires JavaScript, consent, or an access check.'
    elif len(result.text.split()) >= 100 and len(best) >= 2:
        result.status = 'article'
        result.reason = 'Main article text extracted; completeness cannot be guaranteed.'
    elif result.lead:
        result.status, result.reason = 'excerpt', 'Only a short text or description was available; no full-article analysis.'
    else:
        result.status, result.reason = 'unavailable', 'No readable article text found (the site may require JavaScript).'
    return result


class NewsScraper:
    def __init__(self, session=None, log=print):
        self.session = session or requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.log = log
        self.robots = {}

    def _download(self, url):
        for _ in range(6):
            response = self.session.get(url, timeout=30, stream=True, allow_redirects=False)
            with response:
                if response.is_redirect:
                    redirected = normalized_url(response.headers.get('Location'), url)
                    if not redirected or not self.allowed(redirected):
                        raise ValueError('The redirected URL is invalid or disallowed by robots.txt.')
                    url = redirected
                    continue
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError('Response exceeds the 4 MB download limit.')
                    chunks.append(chunk)
                return b''.join(chunks), response.url
        raise ValueError('Too many redirects.')

    def allowed(self, url):
        parsed = urlsplit(url)
        origin = f'{parsed.scheme}://{parsed.netloc}'
        if origin not in self.robots:
            parser = RobotFileParser()
            try:
                response = self.session.get(origin + '/robots.txt', timeout=15)
                try:
                    if response.status_code == 404:
                        parser.parse([])
                    else:
                        response.raise_for_status()
                        parser.parse(response.text.splitlines())
                finally:
                    response.close()
                self.robots[origin] = parser
            except requests.RequestException as error:
                self.log(f'Cannot check robots.txt for {origin}: {error}. Skipping this origin.')
                self.robots[origin] = None
        parser = self.robots[origin]
        return parser is not None and parser.can_fetch(USER_AGENT, url)

    def fetch(self, url):
        url = normalized_url(url, url)
        if not url or not self.allowed(url):
            raise ValueError('URL is invalid or robots.txt does not permit fetching it.')
        document, final_url = self._download(url)
        if final_url != url and not self.allowed(final_url):
            raise ValueError('The redirected URL is disallowed by robots.txt.')
        return document, final_url

    def discover(self, url, selector=None, limit=10, feed_url=None):
        if feed_url:
            document, final_url = self.fetch(feed_url)
            links = parse_feed(document, final_url)
            if links is None:
                raise ValueError('The configured feed URL did not return RSS or Atom.')
            return unique_links(links, url)[:limit]
        document, final_url = self.fetch(url)
        feed_links = parse_feed(document, final_url)
        if feed_links is not None:
            return feed_links[:limit]
        soup = BeautifulSoup(document, 'html.parser')
        if selector:
            return html_article_links(soup, final_url, selector)[:limit]
        # A direct article URL also works as a source.
        metadata = article_metadata(soup)
        page_reference = metadata.get('url') or metadata.get('mainEntityOfPage')
        if isinstance(page_reference, dict):
            page_reference = page_reference.get('@id')
        heading = soup.find('h1')
        matches_heading = (heading and isinstance(metadata.get('headline'), str)
                           and clean(heading.get_text(' ', strip=True)).casefold() == clean(metadata['headline']).casefold())
        matches_url = isinstance(page_reference, str) and normalized_url(page_reference, final_url) == normalized_url(final_url, final_url)
        if meta(soup, 'og:type') == 'article' or (metadata and (matches_url or (not page_reference and matches_heading))):
            return [final_url]
        links = []
        feeds = [element.get('href') for element in soup.select('link[rel~="alternate"]')
                 if element.get('type', '').lower() in ('application/rss+xml', 'application/atom+xml')]
        for feed in unique_links(feeds, final_url, same_domain=False)[:3]:
            try:
                feed_document, feed_final = self.fetch(feed)
                links.extend(parse_feed(feed_document, feed_final) or [])
            except (requests.RequestException, ValueError) as error:
                self.log(f'Feed unavailable at {feed}: {error}. Trying page links.')
        links = unique_links(links, final_url)
        links.extend(html_article_links(soup, final_url))
        return list(dict.fromkeys(links))[:limit]

    def article(self, url):
        try:
            document, final_url = self.fetch(url)
            return extract_article(document, final_url)
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else None
            return Article(url=url, status='paywalled' if status == 402 else 'blocked', reason=f'HTTP {status}; article not read.')
        except (requests.RequestException, ValueError) as error:
            return Article(url=url, reason=str(error))
