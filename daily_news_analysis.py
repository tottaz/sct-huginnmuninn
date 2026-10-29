import argparse
import json
import os
from pathlib import Path
import smtplib
import sys
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

import requests
from openai import OpenAI
from news_scraper import NewsScraper
from analysis_prompt import get_analysis_prompt
from run_events import emit_event
from email_report import render_report
from article_settings import article_limit, DEFAULT_ARTICLE_LIMIT
from related_coverage import summarize_related, title_from_url
from news_history import archive_report

config = {}
client = None


def load_settings(initialize_ai=True):
    global config, client
    directory = Path(__file__).resolve().parent
    filename = 'huginnmuninn-config.json' if Path(__file__).name == 'sct_daily_news_analysis.py' else 'config.json'
    config = json.loads((directory / filename).read_text())
    if initialize_ai:
        get_analysis_prompt(config)
    if initialize_ai and config.get('use_openai'):
        if not config.get('openai_api_key'):
            raise ValueError('OpenAI API key is required when using OpenAI.')
        client = OpenAI(api_key=config['openai_api_key'])


DEFAULT_SITES = [
    'https://www.theguardian.com/world',
    'https://www.theguardian.com/world/europe-news',
    'https://www.aftonbladet.se', 'https://www.expressen.se',
    'https://www.epochtimes.se', 'https://www.svt.se/',
]


def scrape_site(url, selector=None, limit=DEFAULT_ARTICLE_LIMIT):
    """Compatibility wrapper; no publication-specific extraction rules."""
    return NewsScraper().discover(url, selector=selector, limit=limit)


# === Helper function to summarize and analyze article ===
def summarize_and_analyze_article(article_text, is_swedish=False):
    prompt = get_analysis_prompt(config)

    # Add a note if the article is Swedish
    if is_swedish:
        prompt = "This article is in Swedish.\n" + prompt

    if config.get('use_openai'):
        response = client.chat.completions.create(
            model=config.get("openai_model", "gpt-4"),
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": article_text}
            ]
        )
        return response.choices[0].message.content.strip()

    else:
        # Ollama request via POST method (as per your working setup)
        payload = {
            "model": config.get("ollama_model", "llama3.2:latest"),  # Use the appropriate model name for Ollama
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": article_text}
            ]
        }

        response = requests.post(
            f"{config['ollama_base_url'].rstrip('/') if config['ollama_base_url'].rstrip('/').endswith('/v1') else config['ollama_base_url'].rstrip('/') + '/v1'}/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=180
        )

        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        else:
            raise Exception(f"Error with Ollama API: {response.text}")


# === Helper function to send email with list of analysis ===
def send_email(subject, body, html_body=None):
    email = config['email'].strip()
    app_password = ''.join(config['app_password'].split())
    if not app_password:
        raise ValueError('Enter a Google app password before sending email.')
    msg = MIMEMultipart("alternative")
    msg["From"] = email
    msg["To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if html_body is not None:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    stage = 'connecting'
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            stage = 'signing in'
            server.login(email, app_password)
            stage = 'sending'
            rejected = server.sendmail(email, email, msg.as_string())
            if rejected:
                raise RuntimeError("Gmail rejected the recipient.")
        print(f"Email submitted to Gmail for {email}: {subject}")
    except smtplib.SMTPAuthenticationError as error:
        raise RuntimeError('Gmail rejected the sign-in. Use a Google app password for this email address, not your normal Google password. Spaces are removed automatically. Check 2-Step Verification and whether the app password was revoked.') from error
    except smtplib.SMTPServerDisconnected as error:
        if stage == 'signing in':
            message = 'Gmail closed the connection during sign-in. Spaces are removed automatically; check the email address and Google app password. If it continues, try again later or check your network connection.'
        else:
            message = f'Gmail disconnected while {stage}. Check Gmail Sent before retrying if the message may already have been submitted.'
        raise RuntimeError(message) from error
    except Exception as e:
        raise RuntimeError(f"Email delivery failed: {e}") from e


def write_report(results, source_errors):
    """Retain extracted public data and skipped reasons without truncating stored text."""
    path = Path(__file__).resolve().parent / 'news-results.json'
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'articles': results, 'source_errors': source_errors}
    fd, temporary = tempfile.mkstemp(prefix='.news-results-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f'Extraction report: {path}')
    archive_report(path.parent, results, report['generated_at'])
    return path


def process_news(on_event=None):
    publish = on_event or (lambda event: None)
    scraper = NewsScraper()
    results, source_errors, seen = [], [], set()
    for source in config.get('news_sites', DEFAULT_SITES):
        if isinstance(source, str):
            source = {'url': source}
        if not source.get('enabled', True):
            continue
        site = source['url']
        print(f'Finding news from {site}…')
        publish({'type': 'progress', 'message': f'Finding news from {site}…'})
        try:
            links = scraper.discover(site, selector=source.get('selector'),
                                     limit=article_limit(config, source), feed_url=source.get('feed_url'))
            if not links:
                source_errors.append({'url': site, 'reason': 'No article links found. Try an RSS/Atom feed URL or an optional CSS selector.'})
        except Exception as error:
            source_errors.append({'url': site, 'reason': str(error)})
            print(f'Skipping source {site}: {error}')
            continue
        for link in links:
            if link in seen:
                continue
            seen.add(link)
            print(f'Reading {link}…')
            publish({'type': 'article', 'id': link, 'phase': 'reading',
                     'article': {'url': link, 'source': site, 'title': '', 'analysis': ''}})
            article = scraper.article(link)
            if article.url in seen and article.url != link:
                publish({'type': 'article', 'id': link, 'phase': 'skipped',
                         'article': dict(article.to_dict(), source=site, analysis='', reason='Duplicate article after redirect.')})
                continue
            seen.add(article.url)
            result = article.to_dict()
            if not result['title']:
                hint = title_from_url(article.url)
                if hint:
                    result['title'] = hint + ' (from URL)'
            result['source'] = site
            result['analysis'] = ''
            if article.status == 'article':
                publish({'type': 'article', 'id': link, 'phase': 'analyzing', 'article': dict(result)})
                try:
                    text = article.text[:10000]
                    if len(article.text) > 10000:
                        text += '\n[Input truncated to the first 10,000 characters.]'
                    result['analysis'] = summarize_and_analyze_article(
                        f'Title: {article.title}\n\n{text}', is_swedish=article.language.lower().startswith('sv'))
                    if not result['analysis']:
                        raise ValueError('The model returned an empty analysis.')
                except Exception as error:
                    result['analysis_error'] = str(error)
                    print(f'Analysis failed for {link}: {error}')
            elif article.status in ('paywalled', 'blocked', 'unavailable', 'excerpt') and config.get('search_related_coverage', False):
                publish({'type': 'article', 'id': link, 'phase': 'analyzing', 'article': dict(result)})
                try:
                    result.update(summarize_related(article, config))
                except Exception as error:
                    result['analysis_error'] = str(error)
                    print(f'Related coverage search failed for {link}: {error}')
            else:
                print(f'{article.status}: {article.reason}')
            results.append(result)
            phase = 'failed' if result.get('analysis_error') else ('complete' if result['analysis'] else 'skipped')
            publish({'type': 'article', 'id': link, 'phase': phase, 'article': dict(result)})
    write_report(results, source_errors)
    body, html_body = render_report(results, source_errors)
    publish({'type': 'progress', 'message': 'Sending results by email…'})
    send_email('Latest News Headlines and Analysis', body, html_body)
    publish({'type': 'progress', 'message': f'Email submitted to Gmail for {config.get("email", "configured address")}.'})
    return results


def resend_saved_report(on_event=None):
    path = Path(__file__).resolve().parent / 'news-results.json'
    if not path.is_file():
        raise ValueError('No saved report exists yet. Finish an extraction or analysis run first.')
    report = json.loads(path.read_text())
    articles, errors = report.get('articles'), report.get('source_errors', [])
    if not isinstance(articles, list) or not isinstance(errors, list):
        raise ValueError('The saved report has an invalid format.')
    body, html = render_report(articles, errors)
    send_email('Latest News Headlines and Analysis', body, html)
    if on_event:
        on_event({'type': 'progress', 'message': 'Saved report submitted to Gmail.'})


def main():
    parser = argparse.ArgumentParser(description='Discover and analyze publicly accessible news.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--resend-report', action='store_true', help='Send the existing news-results.json without scraping or AI requests.')
    mode.add_argument('--preview', metavar='URL', help='Extract articles without AI requests or email.')
    parser.add_argument('--events', action='store_true', help='Emit structured live progress and article results for the desktop app.')
    parser.add_argument('--limit', type=int, default=DEFAULT_ARTICLE_LIMIT, help='Article limit for extraction-only preview (1–100).')
    args = parser.parse_args()
    try:
        preview_limit = article_limit({'articles_per_site': args.limit})
    except ValueError as error:
        parser.error(str(error))
    if args.preview:
        scraper = NewsScraper()
        results = [scraper.article(url).to_dict() for url in scraper.discover(args.preview, limit=preview_limit)]
        write_report(results, [])
        for item in results:
            print(f"{item['status']}: {item['title']} — {item['url']}")
    elif args.resend_report:
        load_settings(initialize_ai=False)
        resend_saved_report(on_event=emit_event if args.events else None)
    else:
        load_settings()
        process_news(on_event=emit_event if args.events else None)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        print(f'Run failed: {error}', file=sys.stderr, flush=True)
        raise SystemExit(1)
