from email import policy
from email.parser import Parser
import unittest
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
import daily_news_analysis as news
from email_report import markdown_html, render_report

ARTICLES = [dict(title='Climate & community', url='https://example.com/story?x=1&y=2', source='Example News', status='article', reason='Public text extracted.', lead='A lead with Swedish åäö.', analysis='## For the people\n- **Public transport** improves access.\n- Costs remain *uncertain*.\n\n## Next steps\n1. Review evidence\n2. Read [source](https://example.com/report)', text='Full text')]


class EmailReportTests(unittest.TestCase):
    def test_headings_lists_links_and_unicode(self):
        plain, html = render_report(ARTICLES)
        soup = BeautifulSoup(html, 'html.parser')
        self.assertEqual(soup.h1.get_text(), 'Your daily perspective')
        self.assertIn('For the people', [h.get_text() for h in soup.find_all('h3')])
        self.assertEqual(soup.find('strong').get_text(), 'Public transport')
        self.assertTrue(soup.find('ul'))
        self.assertTrue(soup.find('ol'))
        self.assertIn('åäö', html)
        self.assertNotIn('**Public transport**', plain)
        self.assertNotIn('## For the people', soup.get_text())
        self.assertEqual(soup.find('a')['href'], ARTICLES[0]['url'])

    def test_untrusted_html_is_escaped_and_dangerous_urls_are_not_links(self):
        article = dict(ARTICLES[0], title='<img src=x onerror=alert(1)>', url='javascript:alert(1)', lead='<script>alert(1)</script>', analysis='<script>alert(2)</script>\n**Safe bold**')
        _, html = render_report([article])
        soup = BeautifulSoup(html, 'html.parser')
        self.assertIsNone(soup.find('script'))
        self.assertIsNone(soup.find('img'))
        self.assertFalse(any(a.get('href', '').startswith('javascript:') for a in soup.find_all('a')))
        self.assertIn('<script>alert(2)</script>', soup.get_text())

    def test_skips_and_failures_are_in_both_formats(self):
        plain, html = render_report([dict(title='Locked story', url='https://example.com/locked', status='paywalled', reason='Subscription required.', analysis='')], [{'url':'https://down.example','reason':'No article links found.'}])
        for text in [plain, BeautifulSoup(html,'html.parser').get_text()]:
            self.assertIn('Subscription required.', text)
            self.assertIn('No article links found.', text)
        self.assertIn('0 analyzed', BeautifulSoup(html,'html.parser').get_text())

    def test_code_blocks_preserve_literal_content(self):
        html = markdown_html('```html\n<script>example</script>\n```')
        soup = BeautifulSoup(html,'html.parser')
        self.assertIsNone(soup.find('script'))
        self.assertEqual(soup.code.get_text(), '<script>example</script>')

    def test_email_contains_plain_and_html_alternatives(self):
        plain, html = render_report(ARTICLES)
        smtp = Mock()
        smtp.sendmail.return_value = {}
        with patch.object(news, 'config', {'email':'me@example.com','app_password':'secret'}), patch.object(news.smtplib,'SMTP_SSL') as connection:
            connection.return_value.__enter__.return_value = smtp
            news.send_email('Daily news', plain, html)
        message = Parser(policy=policy.default).parsestr(smtp.sendmail.call_args.args[2])
        self.assertEqual(message.get_content_type(),'multipart/alternative')
        self.assertEqual(message['To'],'me@example.com')
        parts=list(message.iter_parts())
        self.assertEqual([part.get_content_type() for part in parts],['text/plain','text/html'])
        self.assertIn('åäö',parts[0].get_content())
        self.assertIn('<strong>Public transport</strong>',parts[1].get_content())
        smtp.login.assert_called_once_with('me@example.com','secret')

    def test_gmail_errors_are_reported_instead_of_logged_as_success(self):
        with patch.object(news, 'config', {'email':'me@example.com','app_password':'secret'}), patch.object(news.smtplib,'SMTP_SSL',side_effect=OSError('Cannot connect')):
            with self.assertRaisesRegex(RuntimeError,'Email delivery failed'):
                news.send_email('Daily news','Plain','<p>HTML</p>')

    def test_preview_writes_html_and_opens_browser_without_sending(self):
        from pathlib import Path
        import tempfile
        import config_ui
        editor = config_ui.Editor.__new__(config_ui.Editor)
        editor.results = {'one': {'article': ARTICLES[0], 'phase': 'complete'}}
        editor.attempt = lambda action: action()
        editor.log = Mock()
        with tempfile.TemporaryDirectory() as temporary, patch.object(config_ui, 'DATA_DIRECTORY', Path(temporary)), patch.object(config_ui.webbrowser, 'open') as browser, patch.object(news, 'send_email') as send:
            editor.preview_email()
            preview = Path(temporary) / 'email-preview.html'
            self.assertIn('<strong>Public transport</strong>', preview.read_text())
            browser.assert_called_once_with(preview.as_uri())
            send.assert_not_called()

    def test_display_spaces_and_unicode_whitespace_are_removed_before_login(self):
        smtp = Mock()
        smtp.sendmail.return_value = {}
        with patch.object(news, 'config', {'email':' me@example.com ','app_password':'abcd efgh\u00a0ijkl\nmnop'}), patch.object(news.smtplib,'SMTP_SSL') as connection:
            connection.return_value.__enter__.return_value = smtp
            news.send_email('Daily news','Plain')
        smtp.login.assert_called_once_with('me@example.com','abcdefghijklmnop')

    def test_disconnect_at_login_is_not_misreported_as_definite_bad_password(self):
        smtp = Mock()
        smtp.login.side_effect = news.smtplib.SMTPServerDisconnected('Connection unexpectedly closed')
        with patch.object(news, 'config', {'email':'me@example.com','app_password':'abcd efgh ijkl mnop'}), patch.object(news.smtplib,'SMTP_SSL') as connection:
            connection.return_value.__enter__.return_value = smtp
            with self.assertRaisesRegex(RuntimeError,'closed the connection during sign-in'):
                news.send_email('Daily news','Plain')
        smtp.sendmail.assert_not_called()

    def test_resend_reads_existing_report_without_scraping_or_ai(self):
        from pathlib import Path
        import tempfile,json
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)
            (directory/'news-results.json').write_text(json.dumps({'articles':ARTICLES,'source_errors':[]}))
            with patch.object(news,'__file__',str(directory/'sct_daily_news_analysis.py')), patch.object(news,'send_email') as send, patch.object(news,'NewsScraper') as scraper, patch.object(news,'summarize_and_analyze_article') as analyze:
                news.resend_saved_report()
            send.assert_called_once()
            self.assertIn('<strong>Public transport</strong>',send.call_args.args[2])
            scraper.assert_not_called()
            analyze.assert_not_called()
