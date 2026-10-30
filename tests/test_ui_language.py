import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ui_language import translate
from config_manager import validate
from config_ui import Editor


class LanguageTests(unittest.TestCase):
    def test_translates_both_directions_and_preserves_dynamic_content(self):
        self.assertEqual(translate('News history', 'sv'), 'Nyhetshistorik')
        self.assertEqual(translate('Nyhetshistorik', 'en'), 'News history')
        title = 'English headline {untouched} & åäö'
        swedish = translate('Analysis ready: {title}', 'sv', title=title)
        self.assertEqual(swedish, 'Analys klar: ' + title)
        self.assertEqual(translate(swedish, 'en'), 'Analysis ready: ' + title)
        self.assertEqual(translate('3 models available.', 'sv'), '3 modeller tillgängliga.')
        self.assertEqual(translate('https://example.com/news', 'sv'), 'https://example.com/news')

    def test_language_validation_and_legacy_default(self):
        config = json.loads(Path('config.example.json').read_text())
        for code in ('sv', 'en'):
            config['appearance']['language'] = code
            validate(config)
        for value in ('de', None, 3):
            config['appearance']['language'] = value
            with self.assertRaises(ValueError):
                validate(config)
        config.pop('appearance')
        validate(config)

    def test_save_default_changes_only_preference(self):
        class Field:
            def get(self): return 'Svenska'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            saved = {'unfinished': 'must stay', 'appearance': {'theme': 'flatly'}}
            path.write_text(json.dumps(saved))
            editor = Editor.__new__(Editor)
            editor.original = copy.deepcopy(saved)
            editor.language = Field()
            editor.attempt = lambda action: action()
            editor.change_language = lambda: None
            editor.log = lambda text: None
            with patch('config_ui.CONFIG', path):
                editor.save_default_language()
            expected = copy.deepcopy(saved)
            expected['appearance']['language'] = 'sv'
            self.assertEqual(json.loads(path.read_text()), expected)
            self.assertEqual(editor.default_language, 'sv')
