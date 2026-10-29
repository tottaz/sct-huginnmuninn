import unittest
from unittest.mock import Mock, patch
from news_scraper import Article
from related_coverage import summarize_related, title_from_url
import daily_news_analysis as news


class RelatedCoverageTests(unittest.TestCase):
    def test_title_hint_skips_publisher_article_id(self):
        url = 'https://www.thestar.com/news/canada/cp-newsalert-at-least-two-canadians-hurt-in-rail-crash-in-spain-carney-says/article_d1b52df7-a540-5bc1-8c11-f0e2f7751bd6.html'
        self.assertEqual(title_from_url(url), 'Cp newsalert at least two canadians hurt in rail crash in spain carney says')
        self.assertEqual(title_from_url('https://example.com/12345'), '')

    def test_search_requires_citations_and_preserves_sources(self):
        response = Mock(status_code=200)
        response.json.return_value = {'steps': [{'type': 'model_output', 'content': [
            {'type': 'text', 'text': 'Related news.', 'annotations': [
                {'type': 'url_citation', 'url': 'https://example.org/story', 'end_index': 13}]}]}]}
        with patch('related_coverage.requests.post', return_value=response) as post:
            result = summarize_related(Article('https://example.com/locked', title='News'), {'gemini_api_key': 'secret'})
            self.assertIn('Summary from related coverage', result['analysis'])
            self.assertIn('[1]', result['analysis'])
            self.assertEqual(result['coverage_sources'], ['https://example.org/story'])
            self.assertEqual(post.call_args.kwargs['json']['tools'], [{'type': 'google_search'}])
            response.json.return_value = {'steps': []}
            with self.assertRaisesRegex(ValueError, 'no cited'):
                summarize_related(Article('https://example.com'), {'gemini_api_key': 'secret'})

    def test_paywall_fallback_is_opt_in_and_failures_do_not_stop_report(self):
        for status in ('paywalled', 'blocked', 'unavailable', 'excerpt'):
          for enabled, fail in [(False, False), (True, False), (True, True)]:
            with self.subTest(status=status, enabled=enabled, fail=fail), patch.object(news, 'config', {
                    'news_sites': ['https://example.com'], 'search_related_coverage': enabled}), \
                    patch.object(news, 'NewsScraper') as scraper, \
                    patch.object(news, 'summarize_related') as search, \
                    patch.object(news, 'write_report'), patch.object(news, 'send_email'):
                scraper.return_value.discover.return_value = ['https://example.com/locked']
                scraper.return_value.article.return_value = Article('https://example.com/locked', status=status, reason='HTTP 429; article not read.')
                search.return_value = {'analysis': 'Summary from related coverage', 'analysis_origin': 'related_coverage'}
                if fail:
                    search.side_effect = ValueError('No matching coverage')
                result = news.process_news()[0]
                self.assertEqual(search.call_count, int(enabled))
                self.assertEqual(result['status'], status)
                self.assertEqual(bool(result.get('analysis_error')), enabled and fail)
                self.assertEqual(bool(result['analysis']), enabled and not fail)
