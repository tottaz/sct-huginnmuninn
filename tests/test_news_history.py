import tempfile
import unittest
from news_history import archive_report, search_history, get_article, delete_entries


class HistoryTests(unittest.TestCase):
    def test_snapshots_search_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            item = {'title': 'Rail update', 'url': 'https://example.com/story',
                    'text': 'Public article body', 'analysis': 'Related coverage with citations'}
            archive_report(directory, [item], '2026-10-29T10:00:00+00:00')
            archive_report(directory, [dict(item, analysis='New information')], '2026-10-30T10:00:00+00:00')
            rows = search_history(directory, 'RAIL')
            self.assertEqual(len(rows), 2)
            self.assertEqual(get_article(directory, rows[1][0]), item)
            self.assertEqual(len(search_history(directory, 'citations')), 1)
            self.assertEqual(search_history(directory, '%'), [])
            delete_entries(directory, [rows[0][0]])
            self.assertEqual(len(search_history(directory)), 1)
            with self.assertRaises(ValueError):
                get_article(directory, rows[0][0])
