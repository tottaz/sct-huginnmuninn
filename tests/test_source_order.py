"""Source ordering keeps each source's settings attached to its row."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from config_ui import Editor


class SourceOrderTests(unittest.TestCase):
    def setUp(self):
        self.editor = Editor.__new__(Editor)
        self.editor.sites = [
            {'url': 'https://a.example', 'enabled': False},
            {'url': 'https://b.example', 'articles_per_site': 5},
            {'url': 'https://c.example', 'feed_url': 'https://c.example/rss'},
        ]
        self.editor.site_table = Mock()
        self.editor.show_sites = Mock()

    def test_moves_in_both_directions_without_losing_settings(self):
        original = list(self.editor.sites)
        self.editor.move_site(0, 2)
        self.assertEqual(self.editor.sites, [original[1], original[2], original[0]])
        self.editor.site_table.selection_set.assert_called_with('2')
        self.editor.move_site(2, 0)
        self.assertEqual(self.editor.sites, original)
        self.assertIs(self.editor.sites[0], original[0])

    def test_keyboard_at_boundary_does_not_wrap(self):
        original = list(self.editor.sites)
        self.editor.site_table.selection.return_value = ('0',)
        self.assertEqual(self.editor.move_selected_site(-1), 'break')
        self.assertEqual(self.editor.sites, original)
        self.editor.show_sites.assert_not_called()

    def test_drop_commits_order_and_clears_drag(self):
        self.editor.site_drag_row = '0'
        self.editor.site_table.identify_row.return_value = '2'
        self.editor.drop_site(SimpleNamespace(y=120))
        self.assertEqual(self.editor.sites[-1]['url'], 'https://a.example')
        self.assertEqual(self.editor.site_drag_row, '')

    def test_header_and_empty_drops_do_not_reorder(self):
        self.editor.site_table.identify_region.return_value = 'heading'
        self.editor.start_site_drag(SimpleNamespace(x=10, y=10))
        self.assertEqual(self.editor.site_drag_row, '')
        self.editor.site_drag_row = '0'
        self.editor.site_table.identify_row.return_value = ''
        self.editor.drop_site(SimpleNamespace(y=400))
        self.editor.show_sites.assert_not_called()
