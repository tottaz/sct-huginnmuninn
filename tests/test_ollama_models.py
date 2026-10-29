import io
import unittest
from unittest.mock import patch
from config_manager import list_ollama_models


class OllamaModelTests(unittest.TestCase):
    def test_native_and_openai_base_urls(self):
        for base in ['http://localhost:11434', 'http://localhost:11434/', 'http://localhost:11434/v1/']:
            with self.subTest(base=base), patch('config_manager.urlopen', return_value=io.BytesIO(b'{"models":[{"name":"z:latest"},{"name":"a:7b"},{"name":"a:7b"}]}')) as request:
                self.assertEqual(list_ollama_models(base), ['a:7b', 'z:latest'])
                request.assert_called_once_with('http://localhost:11434/api/tags', timeout=10)

    def test_no_models(self):
        with patch('config_manager.urlopen', return_value=io.BytesIO(b'{"models":[]}')):
            self.assertEqual(list_ollama_models('http://localhost:11434'), [])

    def test_invalid_response(self):
        for body in [b'{}', b'{"models":[{}]}', b'not json']:
            with self.subTest(body=body), patch('config_manager.urlopen', return_value=io.BytesIO(body)), self.assertRaises(ValueError):
                list_ollama_models('http://localhost:11434')

    def test_server_failure(self):
        with patch('config_manager.urlopen', side_effect=OSError('Connection refused')), self.assertRaises(OSError):
            list_ollama_models('http://localhost:11434')

    def test_invalid_url(self):
        with self.assertRaises(ValueError):
            list_ollama_models('file:///tmp/models')
