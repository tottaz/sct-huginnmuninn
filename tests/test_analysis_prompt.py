import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from analysis_prompt import DEFAULT_ANALYSIS_PROMPT, get_analysis_prompt
import config_manager
import daily_news_analysis as news


class AnalysisPromptTests(unittest.TestCase):
    def test_missing_setting_preserves_existing_prompt(self):
        self.assertEqual(get_analysis_prompt({}), DEFAULT_ANALYSIS_PROMPT)

    def test_legacy_openai_flag_still_uses_ollama(self):
        prompt = 'Return JSON with keys {summary, evidence}.'
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': 'Result'}}]}
        config = {'use_openai': True, 'openai_api_key': 'obsolete',
                  'ollama_base_url': 'http://localhost:11434', 'ollama_model': 'chosen-model', 'analysis_prompt': prompt}
        with patch.object(news, 'config', config), patch.object(news.requests, 'post', return_value=response) as post:
            self.assertEqual(news.summarize_and_analyze_article('Article text'), 'Result')
        self.assertTrue(post.call_args.args[0].startswith('http://localhost:11434/'))
        self.assertEqual(post.call_args.kwargs['json']['model'], 'chosen-model')
        self.assertEqual(post.call_args.kwargs['json']['messages'][0]['content'], prompt)
        self.assertNotIn('obsolete', str(post.call_args))

    def test_ollama_uses_custom_prompt_with_swedish_context(self):
        prompt = 'Explain the evidence in three paragraphs.'
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': 'Analysis'}}]}
        config = {'use_openai': False, 'ollama_base_url': 'http://localhost:11434', 'analysis_prompt': prompt}
        with patch.object(news, 'config', config), patch.object(news.requests, 'post', return_value=response) as post:
            self.assertEqual(news.summarize_and_analyze_article('Svensk artikel', is_swedish=True), 'Analysis')
        self.assertEqual(post.call_args.kwargs['json']['messages'], [
            {'role': 'system', 'content': 'This article is in Swedish.\n' + prompt},
            {'role': 'user', 'content': 'Svensk artikel'}])

    def test_invalid_prompt_fails_before_ai_request(self):
        for value in ['', ' \n ', None, 123, []]:
            with self.subTest(value=value), patch.object(news, 'config', {'analysis_prompt': value}), patch.object(news.requests, 'post') as post:
                with self.assertRaisesRegex(ValueError, 'cannot be blank'):
                    news.summarize_and_analyze_article('Article')
                post.assert_not_called()

    def test_saving_prompt_syncs_existing_deployment(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            config_path = directory / 'settings.json'
            (directory / 'huginnmuninn-deployment.json').write_text('{}')
            config = dict(email='me@example.com', app_password='test', use_openai=True, openai_api_key='obsolete', openai_model='old',
                          ollama_base_url='http://localhost:11434', analysis_prompt='A custom prompt\nwith line breaks.',
                          deployment={'directory': str(directory)})
            with patch.object(config_manager, 'CONFIG', config_path):
                config_manager.save_config(config)
            saved = json.loads(config_path.read_text())
            self.assertEqual(saved['analysis_prompt'], config['analysis_prompt'])
            self.assertFalse({'use_openai', 'openai_api_key', 'openai_model'} & saved.keys())
            self.assertFalse({'use_openai', 'openai_api_key', 'openai_model'} & json.loads((directory / 'huginnmuninn-config.json').read_text()).keys())
            self.assertEqual(json.loads((directory / 'huginnmuninn-config.json').read_text())['analysis_prompt'], config['analysis_prompt'])
