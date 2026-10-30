import unittest
from config_ui import Editor
from config_manager import cron_content


class Field:
    def __init__(self, value): self.value = value
    def get(self): return self.value


class FormTests(unittest.TestCase):
    def test_form_serialization_preserves_unknown_settings(self):
        editor = Editor.__new__(Editor)
        editor.original = {'use_openai': True, 'openai_api_key': 'obsolete', 'openai_model': 'old', 'custom': {'keep': True}, 'schedule': {'custom': 'keep'}}
        editor.fields = {key: Field(value) for key, value in dict(email='me@example.com', app_password=' secret ', ollama_base_url='http://localhost:11434', articles_per_site='5').items()}
        editor.model = Field('gemma4:latest')
        editor.expression = Field('0 10,19 * * *')
        editor.deployment_backups = Field(False)
        editor.sites = [{'url': 'https://example.com', 'enabled': False, 'selector': 'article a'}]
        config = editor.data()
        self.assertEqual(config['articles_per_site'], 5)
        self.assertEqual(config['app_password'], 'secret')
        self.assertEqual(config['ollama_model'], 'gemma4:latest')
        self.assertNotIn('use_openai', config)
        self.assertNotIn('openai_api_key', config)
        self.assertNotIn('openai_model', config)
        self.assertEqual(config['custom'], {'keep': True})
        self.assertEqual(config['schedule'], {'custom': 'keep', 'expression': '0 10,19 * * *'})
        self.assertFalse(config['deployment']['backups'])
        self.assertNotIn('email', editor.original)

    def test_legacy_cron_migration_preserves_mail_jobs(self):
        other = '0 8,17 * * * /usr/bin/python3 /scripts/tbear_gmail_check.py >> /tmp/tbear.log 2>&1\n'
        legacy = '0 10,19 * * * /Library/Frameworks/Python.framework/Versions/3.14/bin/python3 /Users/tottazetterlund/Dev/sct-live-scripts/sct_daily_news_analysis.py >> /tmp/sct_news.log 2>&1\n'
        self.assertEqual(cron_content(other + legacy), other)
        installed = cron_content(other + legacy, '0 10,19 * * *')
        self.assertTrue(installed.startswith(other))
        self.assertNotIn('sct-live-scripts', installed)
        self.assertIn('0 10,19 * * *', installed)
