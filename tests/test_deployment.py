import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import deployment
import config_manager


class DeploymentTests(unittest.TestCase):
    def config(self, directory):
        return dict(email='test@example.com', app_password='test', use_openai=False,
                    ollama_base_url='http://localhost:11434', deployment={'directory': str(directory)})

    def test_deploy_backups_and_dedicated_config(self):
        with tempfile.TemporaryDirectory() as temporary, patch('deployment.bundled_runner', return_value=None), patch('deployment.subprocess.run'):
            directory = Path(temporary)
            script = directory / deployment.SCRIPT_NAME
            script.write_text('old script')
            (directory / 'config-sct.json').write_text('other application settings')
            config = self.config(directory)
            _, backup, previous, command = deployment.deploy(config)
            self.assertEqual((backup / script.name).read_text(), 'old script')
            self.assertEqual(script.read_bytes(), (deployment.ASSETS / 'daily_news_analysis.py').read_bytes())
            self.assertEqual(json.loads((directory / 'huginnmuninn-config.json').read_text()), config)
            self.assertEqual((directory / 'config-sct.json').read_text(), 'other application settings')
            self.assertEqual(command[-1], str(script))
            deployment.rollback(directory, previous)
            self.assertEqual(script.read_text(), 'old script')
            self.assertFalse((directory / 'huginnmuninn-deployment.json').exists())

    def test_worker_and_config_sync(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'live'
            runner = Path(temporary) / 'worker'
            runner.write_bytes(b'worker binary')
            with patch('deployment.bundled_runner', return_value=runner):
                config = self.config(directory)
                deployment.deploy(config)
            self.assertEqual(deployment.deployed_command(config), [str(directory / deployment.RUNNER_NAME)])
            config['ollama_model'] = 'new:latest'
            deployment.sync_deployed_config(config)
            self.assertEqual(json.loads((directory / 'huginnmuninn-config.json').read_text())['ollama_model'], 'new:latest')

    def test_backups_can_be_disabled_and_managed(self):
        with tempfile.TemporaryDirectory() as temporary, patch('deployment.bundled_runner', return_value=None), patch('deployment.subprocess.run'):
            directory = Path(temporary)
            (directory / deployment.SCRIPT_NAME).write_text('old script')
            config = self.config(directory)
            config['deployment']['backups'] = False
            _, backup, _, _ = deployment.deploy(config)
            self.assertIsNone(backup)
            self.assertEqual(deployment.list_backups(config), [])

            config['deployment']['backups'] = True
            _, backup, _, _ = deployment.deploy(config)
            self.assertIsNotNone(backup)
            versions = deployment.list_backups(config)
            self.assertEqual([item['name'] for item in versions], [backup.name])
            self.assertGreater(versions[0]['files'], 0)
            self.assertEqual(deployment.delete_backups(config, [backup.name]), [backup.name])
            self.assertEqual(deployment.list_backups(config), [])

    def test_failed_cron_install_restores_previous_deployment(self):
        with tempfile.TemporaryDirectory() as temporary, patch('deployment.bundled_runner', return_value=None), patch('config_manager.read_crontab', return_value=''):
            directory = Path(temporary)
            script = directory / deployment.SCRIPT_NAME
            script.write_text('old version')
            def execute(command, **kwargs):
                from subprocess import CompletedProcess
                return CompletedProcess(command, 1 if command == ['crontab', '-'] else 0, '', 'cron rejected')
            with patch('subprocess.run', side_effect=execute), self.assertRaisesRegex(RuntimeError, 'cron rejected'):
                config_manager.update_cron('0 10,19 * * *', self.config(directory))
            self.assertEqual(script.read_text(), 'old version')
            self.assertFalse((directory / 'huginnmuninn-config.json').exists())

    def test_cron_uses_deployed_worker_with_quoted_paths(self):
        content = config_manager.cron_content('', '0 10,19 * * *', ['/tmp/live folder/news-runner'], Path('/tmp/live folder'))
        self.assertIn("cd '/tmp/live folder'", content)
        self.assertIn("'/tmp/live folder/news-runner'", content)
