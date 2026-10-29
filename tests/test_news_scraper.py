import unittest
from unittest.mock import Mock, patch
import requests
from bs4 import BeautifulSoup
from news_scraper import Article, NewsScraper, extract_article, html_article_links, normalized_url, parse_feed
import daily_news_analysis as news

URL = 'https://example.com/news'
PARAGRAPH = 'Residents met at the town hall to discuss the new public transport service and how it will improve access to schools and local jobs. '
FULL = f'<html lang="sv"><head><meta property="og:title" content="New public transport plan"></head><body><nav><p>Navigation should never be extracted.</p></nav><article><h1>New public transport plan</h1><p>{PARAGRAPH * 3}</p><p>Officials described the next steps. {PARAGRAPH * 3}</p><aside><p>Related stories should not appear here.</p></aside></article><footer><p>Subscribe to our newsletter.</p></footer></body></html>'


class FakeSession:
    def __init__(self, pages):
        self.headers = {}
        self.pages = pages
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        status, body, headers = self.pages[url]
        response = requests.Response()
        response.status_code = status
        response._content = body.encode()
        response._content_consumed = True
        response.url = url
        response.headers.update(headers)
        return response


class ExtractionTests(unittest.TestCase):
    def test_full_article_title_lead_language_and_boilerplate(self):
        article = extract_article(FULL, URL)
        self.assertEqual(article.status, 'article')
        self.assertEqual(article.title, 'New public transport plan')
        self.assertEqual(article.language, 'sv')
        self.assertTrue(article.lead.startswith('Residents met'))
        self.assertNotIn('Navigation', article.text)
        self.assertNotIn('Related stories', article.text)
        self.assertNotIn('newsletter', article.text)

    def test_jsonld_paywall_does_not_extract_embedded_body(self):
        for accessible in [False, 'false']:
            import json
            markup = json.dumps({'@graph': [{'@type': 'NewsArticle', 'headline': 'Subscriber headline', 'isAccessibleForFree': accessible, 'articleBody': 'Hidden full article'}]})
            article = extract_article(f'<script type="application/ld+json">{markup}</script>' + FULL, URL)
            self.assertEqual(article.status, 'paywalled')
            self.assertEqual(article.text, '')
            self.assertEqual(article.lead, '')

    def test_visible_paywall_and_access_gate(self):
        for markup, expected in [('<h1>Story</h1><p>Subscribe to continue reading</p>', 'paywalled'), ('<h1>Access denied</h1><p>Please verify you are human</p>', 'blocked'), ('<div class="paywall"><p>Members only</p></div>', 'paywalled')]:
            with self.subTest(markup=markup):
                article = extract_article(markup, URL)
                self.assertEqual(article.status, expected)
                self.assertEqual(article.text, '')

    def test_excerpt_and_empty_page_are_not_full_articles(self):
        short = extract_article('<h1>Story</h1><meta name="description" content="A short public description">', URL)
        self.assertEqual(short.status, 'excerpt')
        self.assertEqual(short.lead, 'A short public description')
        self.assertEqual(extract_article('<h1>Story</h1>', URL).status, 'unavailable')

    def test_hidden_content_and_comments_not_used(self):
        markup = f'<h1>Story</h1><div hidden><p>{PARAGRAPH * 10}</p></div><div class="comments"><p>{PARAGRAPH * 10}</p></div>'
        self.assertEqual(extract_article(markup, URL).text, '')


class DiscoveryTests(unittest.TestCase):
    def test_normalization_and_feed_formats(self):
        self.assertEqual(normalized_url('/story?utm_source=x&id=2#share', URL), 'https://example.com/story?id=2')
        self.assertIsNone(normalized_url('javascript:alert(1)', URL))
        self.assertEqual(parse_feed('<rss><channel><item><link>/article-one</link></item><item><link>/article-one#top</link></item></channel></rss>', URL), ['https://example.com/article-one'])
        self.assertEqual(parse_feed('<feed xmlns="http://www.w3.org/2005/Atom"><entry><link rel="self" href="/api"/><link href="/story"/></entry></feed>', URL), ['https://example.com/story'])
        self.assertIsNone(parse_feed('<html></html>', URL))

    def test_general_html_discovery_excludes_nav_and_external_links(self):
        html = '<nav><a href="/navigation"><h2>Navigation menu title here</h2></a></nav><article><h2><a href="/story">Residents discuss new local service</a></h2></article><a href="https://advert.example/ad"><h2>Sponsored external news headline here</h2></a><a href="/privacy">Privacy policy</a>'
        self.assertEqual(html_article_links(BeautifulSoup(html, 'html.parser'), URL), ['https://example.com/story'])

    def test_feed_discovery_and_fallback_if_feed_unavailable(self):
        html = '<link rel="alternate" type="application/rss+xml" href="/rss"><article><a href="/fallback"><h2>Local news from town hall</h2></a></article>'
        for status, body, expected in [(200, '<rss><channel><item><link>/feed-story</link></item></channel></rss>', '/feed-story'), (500, '', '/fallback')]:
            session = FakeSession({'https://example.com/robots.txt': (200, 'User-agent: *\nAllow: /', {}), URL: (200, html, {}), 'https://example.com/rss': (status, body, {})})
            scraper = NewsScraper(session, log=lambda text: None)
            self.assertEqual(scraper.discover(URL, limit=1), ['https://example.com' + expected])
            self.assertEqual(session.calls.count('https://example.com/robots.txt'), 1)

    def test_selector_override_and_direct_article_url(self):
        session = FakeSession({'https://example.com/robots.txt': (404, '', {}), URL: (200, '<a class="chosen" href="/custom">Short</a><meta property="og:type" content="article">', {})})
        scraper = NewsScraper(session)
        self.assertEqual(scraper.discover(URL, selector='a.chosen'), ['https://example.com/custom'])
        self.assertEqual(scraper.discover(URL), [URL])

    def test_robots_disallow_prevents_article_request(self):
        session = FakeSession({'https://example.com/robots.txt': (200, 'User-agent: *\nDisallow: /news', {})})
        self.assertEqual(NewsScraper(session).article(URL).status, 'unavailable')
        self.assertNotIn(URL, session.calls)

    def test_redirect_checks_robots_before_requesting_destination(self):
        session = FakeSession({'https://example.com/robots.txt': (200, 'User-agent: *\nDisallow: /private', {}), URL: (302, '', {'Location': '/private/story'})})
        self.assertEqual(NewsScraper(session).article(URL).status, 'unavailable')
        self.assertNotIn('https://example.com/private/story', session.calls)

    def test_http_paywall_vs_access_denied(self):
        for status, expected in [(402, 'paywalled'), (403, 'blocked')]:
            session = FakeSession({'https://example.com/robots.txt': (404, '', {}), URL: (status, '', {})})
            self.assertEqual(NewsScraper(session).article(URL).status, expected)


class ProcessingTests(unittest.TestCase):
    def test_source_failure_deduplication_and_no_ai_for_excerpts_or_paywalls(self):
        scraper = Mock()
        scraper.discover.side_effect = [ValueError('source down'), ['https://example.com/full', 'https://example.com/short', 'https://example.com/locked'], ['https://example.com/full']]
        scraper.article.side_effect = [Article(url='https://example.com/full', title='Full title', text=PARAGRAPH * 6, lead=PARAGRAPH, language='sv', status='article'), Article(url='https://example.com/short', title='Short title', lead='Public teaser', status='excerpt'), Article(url='https://example.com/locked', title='Locked title', status='paywalled')]
        config = {'news_sites': ['https://down.example', URL, 'https://example.com/other']}
        with patch.object(news, 'config', config), patch.object(news, 'NewsScraper', return_value=scraper), patch.object(news, 'summarize_and_analyze_article', return_value='Analysis') as analyze, patch.object(news, 'send_email') as email, patch.object(news, 'write_report') as report:
            results = news.process_news()
        self.assertEqual(len(results), 3)
        self.assertEqual(analyze.call_count, 1)
        self.assertIn('Full title', analyze.call_args.args[0])
        self.assertTrue(analyze.call_args.kwargs['is_swedish'])
        self.assertEqual(len(report.call_args.args[1]), 1)
        self.assertIn('Public teaser', email.call_args.args[1])
        self.assertIn('paywalled', email.call_args.args[1])

class DiscoveryRegressionTests(unittest.TestCase):
    def test_listing_with_nested_article_schema_is_not_a_direct_article(self):
        html = '<script type="application/ld+json">{"@type":"ItemList","itemListElement":[{"@type":"NewsArticle","headline":"Story","url":"https://example.com/story"}]}</script><h1>Latest news</h1><article><a href="/story"><h2>New public transport announced today</h2></a></article>'
        session = FakeSession({'https://example.com/robots.txt': (404, '', {}), URL: (200, html, {})})
        self.assertEqual(NewsScraper(session).discover(URL), ['https://example.com/story'])

    def test_direct_feed_can_link_to_publisher_on_another_host(self):
        feed = '<rss><channel><item><link>https://publisher.example/story</link></item></channel></rss>'
        session = FakeSession({'https://example.com/robots.txt': (404, '', {}), URL: (200, feed, {})})
        self.assertEqual(NewsScraper(session).discover(URL), ['https://publisher.example/story'])
