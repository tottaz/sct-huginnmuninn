import queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from article_settings import article_limit
from config_manager import validate
from config_ui import Editor
from news_scraper import Article
from result_formatting import markdown_spans


class LimitTests(unittest.TestCase):
    def test_default_saved_global_and_site_override(self):
        self.assertEqual(article_limit({}), 1)
        self.assertEqual(article_limit({'articles_per_site': 7}), 7)
        self.assertEqual(article_limit({'articles_per_site': 7}, {'articles_per_site': 2}), 2)
        self.assertEqual(article_limit({'articles_per_site': 7}, {'url': 'https://example.com'}), 7)

    def test_invalid_limits_are_rejected_including_site_overrides(self):
        for value in [0, 101, True, '2', 1.5]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                article_limit({}, {'articles_per_site': value})
        config=dict(email='test', app_password='test', use_openai=False, ollama_base_url='http://localhost:11434', news_sites=[{'url':'https://example.com', 'articles_per_site':0}])
        with self.assertRaises(ValueError):
            validate(config)

    def test_preview_obeys_current_unsaved_limit_and_sends_result_entries(self):
        for override, expected in [(None, 2), (1, 1)]:
            with self.subTest(override=override):
                editor=Editor.__new__(Editor)
                editor.preview_active=False
                editor.process=None
                editor.run_id=0
                editor.fields={'articles_per_site':SimpleNamespace(get=lambda:'2')}
                source={'url':'https://example.com'}
                if override is not None:
                    source['articles_per_site']=override
                editor.sites=[source]
                editor.site_table=Mock()
                editor.site_table.selection.return_value=('0',)
                editor.events=queue.Queue()
                editor.clear_results=Mock()
                editor.tabs=Mock()
                editor.results_page=object()
                editor.run_status=Mock()
                editor.set_running=Mock()
                editor.log=Mock()
                scraper=Mock()
                scraper.discover.return_value=['https://example.com/one','https://example.com/two','https://example.com/three']
                scraper.article.side_effect=lambda url:Article(url=url,title='News',lead='Lead paragraph',text='Article body',status='article')
                with patch('config_ui.NewsScraper',return_value=scraper), patch('config_ui.threading.Thread',side_effect=lambda target,daemon:SimpleNamespace(start=target)):
                    editor.preview_site()
                self.assertEqual(scraper.discover.call_args.kwargs['limit'],expected)
                self.assertEqual(scraper.article.call_count,expected)
                events=[]
                while not editor.events.empty():events.append(editor.events.get_nowait())
                extracted=[event[2] for event in events if event[0]=='run-event' and event[2].get('phase')=='extracted']
                self.assertEqual(len(extracted),expected)
                self.assertEqual(extracted[0]['article']['lead'],'Lead paragraph')
                self.assertEqual(events[-1],('run-finished',1,0))
                editor.tabs.select.assert_called_with(editor.results_page)


class FormattingTests(unittest.TestCase):
    def test_headings_bold_lists_and_inline_code_are_styled_without_raw_markers(self):
        spans=list(markdown_spans('## Main findings\n- **Evidence** is strong\n1. Read `source` first\n'))
        rendered=''.join(text for text,tags in spans)
        self.assertIn('Main findings',rendered)
        self.assertIn('• Evidence is strong',rendered)
        self.assertNotIn('##',rendered)
        self.assertNotIn('**',rendered)
        self.assertTrue(any('heading' in tags for text,tags in spans if 'Main findings' in text))
        self.assertTrue(any('strong' in tags for text,tags in spans if text=='Evidence'))
        self.assertTrue(any('code' in tags for text,tags in spans if text=='source'))

    def test_fenced_code_preserves_literal_markdown(self):
        spans=list(markdown_spans('```text\n**literal**\n```'))
        self.assertEqual(spans,[('**literal**\n',('codeblock',))])
