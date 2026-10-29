import unittest
from config_manager import BEGIN, END, cron_content, validate, validate_cron


class ConfigTests(unittest.TestCase):
    def test_cron_preserves_other_jobs_and_replaces_ours(self):
        other = 'MAILTO=test@example.com\n5 * * * * /usr/bin/other\n'
        installed = cron_content(other, '0 8,20 * * *')
        self.assertTrue(installed.startswith(other))
        updated = cron_content(installed, '15 9 * * 1-5')
        self.assertEqual(updated.count(BEGIN), 1)
        self.assertIn('15 9 * * 1-5', updated)
        self.assertEqual(cron_content(updated), other)

    def test_invalid_cron(self):
        for expression in ['60 * * * *', '* 24 * * *', '* * * * *\necho bad', '*/0 * * * *', '* * * * 6-2']:
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                validate_cron(expression)

    def test_malformed_markers(self):
        with self.assertRaises(ValueError):
            cron_content(BEGIN)
        with self.assertRaises(ValueError):
            cron_content(END + '\n' + BEGIN)

    def test_sites_and_legacy_config(self):
        config = dict(email='a@b.com', app_password='password', ollama_base_url='http://localhost:11434', use_openai=False)
        validate(config)
        config['news_sites'] = [{'url': 'https://example.com', 'selector': 'article a', 'enabled': False}]
        validate(config)
        config['news_sites'][0]['url'] = 'file:///etc/passwd'
        with self.assertRaises(ValueError):
            validate(config)


if __name__ == '__main__':
    unittest.main()
