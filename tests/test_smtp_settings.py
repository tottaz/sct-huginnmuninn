from email import policy
from email.parser import Parser
from pathlib import Path
import json
import smtplib
import tempfile
import unittest
from unittest.mock import Mock, patch

import config_manager
import daily_news_analysis as news
from smtp_settings import settings, connection, test_connection as check_connection


class SMTPTests(unittest.TestCase):
    def custom(self, **overrides):
        smtp = dict(host='mail.example.org', port=587, security='starttls',
                    username='account-name', sender='sender@example.org', authenticate=True)
        smtp.update(overrides)
        return dict(email='reader@example.net', app_password=' leading and internal spaces ', smtp=smtp)

    def test_legacy_gmail_defaults_and_password_spacing(self):
        value = settings({'email': ' me@example.com ', 'app_password': 'abcd efgh\u00a0ijkl'})
        self.assertEqual((value['host'], value['port'], value['security']), ('smtp.gmail.com', 465, 'ssl'))
        self.assertEqual(value['username'], 'me@example.com')
        self.assertEqual(value['sender'], 'me@example.com')
        self.assertEqual(value['password'], 'abcdefghijkl')

    def test_custom_credentials_are_preserved_on_save_and_send(self):
        config = self.custom()
        config['ollama_base_url'] = 'http://localhost:11434'
        self.assertEqual(settings(config)['password'], config['app_password'])
        with tempfile.TemporaryDirectory() as folder, patch.object(config_manager, 'CONFIG', Path(folder) / 'config.json'), patch.object(config_manager, 'sync_deployed_config'):
            config_manager.save_config(config)
            saved = json.loads((Path(folder) / 'config.json').read_text())
            self.assertEqual(saved['app_password'], config['app_password'])
            self.assertEqual(saved['smtp'], config['smtp'])
        server = Mock()
        server.sendmail.return_value = {}
        with patch.object(news, 'config', config), patch('smtplib.SMTP') as factory:
            factory.return_value.__enter__.return_value = server
            news.send_email('News', 'Plain åäö', '<p>HTML åäö</p>')
        factory.assert_called_once_with('mail.example.org', 587, timeout=30)
        server.login.assert_called_once_with('account-name', ' leading and internal spaces ')
        sender, recipient, raw = server.sendmail.call_args.args
        self.assertEqual((sender, recipient), ('sender@example.org', 'reader@example.net'))
        message = Parser(policy=policy.default).parsestr(raw)
        self.assertEqual(message['From'], sender)
        self.assertEqual(message['To'], recipient)
        self.assertEqual(message.get_content_type(), 'multipart/alternative')

    def test_starttls_is_verified_and_happens_before_login(self):
        server = Mock()
        with patch('smtplib.SMTP') as factory:
            factory.return_value.__enter__.return_value = server
            with connection(settings(self.custom())):
                pass
        self.assertEqual([call[0] for call in server.mock_calls], ['ehlo', 'starttls', 'ehlo', 'login'])
        context = server.starttls.call_args.kwargs['context']
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, 2)

    def test_tls_failure_never_authenticates_or_sends(self):
        server = Mock()
        server.starttls.side_effect = smtplib.SMTPNotSupportedError('No TLS')
        with patch('smtplib.SMTP') as factory, patch('smtplib.SMTP_SSL') as ssl_factory:
            factory.return_value.__enter__.return_value = server
            with self.assertRaises(smtplib.SMTPNotSupportedError):
                with connection(settings(self.custom())):
                    server.sendmail('should', 'not', 'happen')
            ssl_factory.assert_not_called()
        server.login.assert_not_called()
        server.sendmail.assert_not_called()

    def test_ssl_uses_verified_context(self):
        with patch('smtplib.SMTP_SSL') as factory, patch('smtplib.SMTP') as plain:
            with connection(settings(self.custom(port=465, security='ssl'))):
                pass
        plain.assert_not_called()
        self.assertTrue(factory.call_args.kwargs['context'].check_hostname)
        self.assertEqual(factory.call_args.args, ('mail.example.org', 465))

    def test_unauthenticated_relay_and_connection_test_do_not_send(self):
        config = self.custom(port=25, security='none', authenticate=False)
        config['app_password'] = ''
        server = Mock()
        server.noop.return_value = (250, b'OK')
        with patch('smtplib.SMTP') as factory:
            factory.return_value.__enter__.return_value = server
            self.assertIn('succeeded', check_connection(config))
        server.login.assert_not_called()
        server.starttls.assert_not_called()
        server.sendmail.assert_not_called()

    def test_invalid_settings_fail_before_connection(self):
        for overrides in ({'port': 0}, {'port': True}, {'port': '587'}, {'security': 'invalid'}, {'host': 'https://mail.example'}, {'host': 'bad\nhost'}, {'authenticate': 'false'}, {'sender': 'sender\nBcc: injected'}):
            with self.subTest(overrides=overrides), patch('smtplib.SMTP') as factory, self.assertRaises(ValueError):
                settings(self.custom(**overrides))
            factory.assert_not_called()

    def test_non_gmail_authentication_errors_are_provider_neutral(self):
        with patch.object(news, 'config', self.custom()), patch('smtplib.SMTP', side_effect=smtplib.SMTPAuthenticationError(535, b'denied')):
            with self.assertRaisesRegex(RuntimeError, 'SMTP server rejected the sign-in'):
                news.send_email('News', 'Body')
