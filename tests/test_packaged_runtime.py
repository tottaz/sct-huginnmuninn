"""Opt-in offline regression for dynamic-script dependencies in the built worker."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from deployment import ASSETS, RUNNER_NAME
from run_events import parse_event


@unittest.skipUnless(os.environ.get('TEST_PACKAGED_RUNTIME') == '1', 'Set TEST_PACKAGED_RUNTIME=1 after building the runtime.')
class PackagedRuntimeTests(unittest.TestCase):
    def test_deployed_script_help_loads_all_dependencies_without_network(self):
        with tempfile.TemporaryDirectory(prefix='huginn-runtime-test-') as temporary:
            directory = Path(temporary)
            shutil.copy2(ASSETS / 'dist' / RUNNER_NAME, directory / RUNNER_NAME)
            shutil.copy2(ASSETS / 'daily_news_analysis.py', directory / 'sct_daily_news_analysis.py')
            shutil.copy2(ASSETS / 'news_scraper.py', directory / 'news_scraper.py')
            result = subprocess.run([str(directory / RUNNER_NAME), '--help'], cwd=directory, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Discover and analyze publicly accessible news', result.stdout, result.stderr)
            self.assertIn('--preview', result.stdout)
            self.assertIn('--events', result.stdout)


    def test_bundled_analysis_emits_live_results_without_network(self):
        script = """import daily_news_analysis as news
from news_scraper import Article
from run_events import emit_event
class Scraper:
    def discover(self, *args, **kwargs):
        return ['https://example.com/story']
    def article(self, url):
        return Article(url=url, title='Offline headline', lead='A public lead.', text='Public article body.', status='article')
news.config = {'news_sites': ['https://example.com']}
news.NewsScraper = Scraper
news.summarize_and_analyze_article = lambda *args, **kwargs: 'Offline analysis result.'
news.write_report = lambda *args: None
news.send_email = lambda *args: None
news.process_news(on_event=emit_event)
"""
        with tempfile.TemporaryDirectory(prefix='huginn-events-test-') as temporary:
            directory = Path(temporary)
            shutil.copy2(ASSETS / 'dist' / RUNNER_NAME, directory / RUNNER_NAME)
            (directory / 'sct_daily_news_analysis.py').write_text(script)
            result = subprocess.run([str(directory / RUNNER_NAME), '--events'], cwd=directory, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            events = [event for line in result.stdout.splitlines() if (event := parse_event(line))]
            articles = [event for event in events if event['type'] == 'article']
            self.assertEqual([event['phase'] for event in articles], ['reading', 'analyzing', 'complete'])
            self.assertEqual(articles[-1]['article']['analysis'], 'Offline analysis result.')
