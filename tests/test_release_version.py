from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_app
from release_version import reserve_version
from app_version import support_summary


class ReleaseVersionTests(unittest.TestCase):
    def test_each_full_build_reserves_the_next_patch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'VERSION').write_text('1.0.0\n')
            self.assertEqual(reserve_version(root),'1.0.1')
            self.assertEqual(reserve_version(root),'1.0.2')
            self.assertEqual((root/'VERSION').read_text(),'1.0.2\n')

    def test_explicit_new_release_becomes_base_for_next_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'VERSION').write_text('1.0.2')
            self.assertEqual(reserve_version(root,'1.1.0'),'1.1.0')
            self.assertEqual(reserve_version(root),'1.1.1')
            with self.assertRaises(ValueError):reserve_version(root,'1.1.1')
            self.assertFalse((root/'.build-version.lock').exists())

    def test_reservation_lock_prevents_overlapping_version_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'VERSION').write_text('1.0.2')
            (root/'.build-version.lock').write_text('test')
            with self.assertRaisesRegex(RuntimeError,'Another build'):
                reserve_version(root)
            self.assertEqual((root/'VERSION').read_text(),'1.0.2')

    def test_dmg_only_keeps_existing_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'VERSION').write_text('1.0.2')
            with patch.object(build_app,'ROOT',root),patch.object(build_app,'DIST',root/'dist'),patch.object(build_app,'package_dmg',return_value=root/'release.dmg'):
                build_app.build(dmg_only=True)
            self.assertEqual((root/'VERSION').read_text(),'1.0.2')

    def test_support_summary_contains_version_and_no_settings(self):
        with patch('app_version.build_info',return_value={'version':'1.0.3','build_id':'abcdef12'}):
            text=support_summary()
        self.assertIn('Version: 1.0.3',text)
        self.assertIn('Build: abcdef12',text)
        self.assertIn('Python:',text)
        self.assertNotIn('password',text.lower())
