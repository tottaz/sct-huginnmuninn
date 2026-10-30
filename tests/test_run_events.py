import contextlib
import io
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import daily_news_analysis as news
from news_scraper import Article
from run_events import emit_event, parse_event
from config_ui import Editor
import ui_launcher


class RunEventTests(unittest.TestCase):
    def test_wire_protocol_preserves_multiline_unicode_and_json_like_content(self):
        event = {'type': 'article', 'id': 'url', 'phase': 'complete',
                 'article': {'analysis': 'First line\nSvenska åäö {"value": 1}', 'title': 'Title'}}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            emit_event(event)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(parse_event(output.getvalue()), event)
        for bad in ['normal output', 'HUGINN_EVENT not json', 'HUGINN_EVENT []', 'HUGINN_EVENT {"type":"article","id":1,"article":{}}']:
            self.assertIsNone(parse_event(bad))

    def test_article_is_published_before_model_and_completed_after_it(self):
        scraper = Mock()
        scraper.discover.return_value = ['https://example.com/one', 'https://example.com/locked']
        scraper.article.side_effect = [Article(url='https://example.com/one', title='News', text='The body', lead='Lead', status='article'),
                                       Article(url='https://example.com/locked', title='Locked', status='paywalled', reason='Subscribers only')]
        events = []
        def analyze(*args, **kwargs):
            self.assertEqual(events[-1]['phase'], 'analyzing')
            self.assertEqual(events[-1]['article']['title'], 'News')
            self.assertEqual(events[-1]['article']['analysis'], '')
            return 'The full returned analysis.'
        with patch.object(news, 'config', {'news_sites': ['https://example.com']}), patch.object(news, 'NewsScraper', return_value=scraper), patch.object(news, 'summarize_and_analyze_article', side_effect=analyze), patch.object(news, 'write_report'), patch.object(news, 'send_email'):
            news.process_news(on_event=events.append)
        article_events = [item for item in events if item['type'] == 'article']
        self.assertEqual([item['phase'] for item in article_events], ['reading', 'analyzing', 'complete', 'reading', 'skipped'])
        self.assertEqual(article_events[2]['article']['analysis'], 'The full returned analysis.')
        self.assertEqual(events[-2]['message'], 'Sending results by email…')
        self.assertIn('Email submitted to the SMTP server', events[-1]['message'])

    def test_messages_from_earlier_runs_cannot_change_current_run(self):
        editor = Editor.__new__(Editor)
        editor.run_id = 2
        editor.log = Mock()
        editor.upsert_result = Mock()
        editor.handle_run_message(('run-log', 1, 'old line'))
        editor.handle_run_message(('run-event', 1, {'type': 'article'}))
        editor.log.assert_not_called()
        editor.upsert_result.assert_not_called()

    def test_duplicate_start_focuses_results_without_redeploying(self):
        editor = Editor.__new__(Editor)
        editor.process = Mock()
        editor.process.poll.return_value = None
        editor.tabs = Mock()
        editor.results_page = object()
        editor.log = Mock()
        editor.save = Mock()
        editor.run()
        editor.tabs.select.assert_called_once_with(editor.results_page)
        editor.save.assert_not_called()


class LauncherTests(unittest.TestCase):
    def test_existing_environment_is_selected_when_theme_package_is_missing(self):
        def find_spec(module):
            return None if module == 'ttkbootstrap' else object()
        with patch.object(ui_launcher.importlib.util, 'find_spec', side_effect=find_spec), patch.object(ui_launcher.Path, 'is_file', return_value=True), patch.object(ui_launcher.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), patch.object(ui_launcher.os, 'execv', side_effect=RuntimeError('relaunched')) as execute:
            with self.assertRaisesRegex(RuntimeError, 'relaunched'):
                ui_launcher.ensure_ui_runtime('/tmp/project/config_ui.py')
        self.assertIn('.venv', execute.call_args.args[0])

    def test_missing_environment_explains_install_instead_of_raw_import_error(self):
        with patch.object(ui_launcher.importlib.util, 'find_spec', return_value=None), patch.object(ui_launcher.Path, 'is_file', return_value=False):
            with self.assertRaises(SystemExit) as error:
                ui_launcher.ensure_ui_runtime('/tmp/project/config_ui.py')
        self.assertIn('-m pip install -r', str(error.exception))
        self.assertIn('ttkbootstrap', str(error.exception))
