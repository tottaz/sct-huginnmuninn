from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch
import build_app
from app_version import APP_ID, APP_NAME
from mac_installer import install_app


def make_app(path, payload='new', identifier=APP_ID):
    executable = path / 'Contents' / 'MacOS' / APP_NAME
    executable.parent.mkdir(parents=True)
    executable.write_text(payload)
    info = dict(CFBundleExecutable=APP_NAME, CFBundleIdentifier=identifier,
                CFBundleShortVersionString='1.0.0', HuginnBuildID='test1234')
    (path/'Contents'/'Info.plist').write_bytes(plistlib.dumps(info))


class MacInstallerTests(unittest.TestCase):
    def test_update_preserves_old_app_and_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            source=root/'image'/f'{APP_NAME}.app'
            destination=root/'Applications'/f'{APP_NAME}.app'
            make_app(source)
            make_app(destination,'old',APP_NAME)
            settings=root/'settings.json'
            settings.write_text('keep settings')
            backup=install_app(source,destination,root/'backups',check_running=lambda app:False)
            executable=Path('Contents')/'MacOS'/APP_NAME
            self.assertEqual((destination/executable).read_text(),'new')
            self.assertEqual((backup/executable).read_text(),'old')
            self.assertEqual(settings.read_text(),'keep settings')

    def test_running_app_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            source=root/'new.app'; destination=root/'installed.app'
            make_app(source);make_app(destination,'old')
            with self.assertRaisesRegex(ValueError,'Quit the installed'):
                install_app(source,destination,root/'backups',check_running=lambda app:True)
            self.assertEqual((destination/'Contents'/'MacOS'/APP_NAME).read_text(),'old')

    def test_failed_replacement_rolls_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            source=root/'new.app'; destination=root/'installed.app'
            make_app(source);make_app(destination,'old')
            rename=Path.rename
            def fail_staging(path,target):
                if path.name.startswith('.huginn-install-'):
                    raise OSError('simulated rename failure')
                return rename(path,target)
            with patch.object(Path,'rename',fail_staging), self.assertRaisesRegex(OSError,'simulated'):
                install_app(source,destination,root/'backups',check_running=lambda app:False)
            self.assertEqual((destination/'Contents'/'MacOS'/APP_NAME).read_text(),'old')


class DmgPublishTests(unittest.TestCase):
    def test_failed_image_creation_preserves_last_working_dmg(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'build').mkdir()
            app=root/f'{APP_NAME}.app';make_app(app)
            output=root/'release.dmg';output.write_bytes(b'last good image')
            def failed(*args):raise RuntimeError('disk image tool blocked')
            with patch.object(build_app,'ROOT',root), patch.object(build_app,'validate_app_launch'),self.assertRaisesRegex(RuntimeError,'blocked'):
                build_app.package_dmg(app,output,runner=failed)
            self.assertEqual(output.read_bytes(),b'last good image')

    def test_verified_image_is_published_with_installer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'build').mkdir()
            app=root/f'{APP_NAME}.app';make_app(app)
            output=root/'Huginn-Muninn.dmg'
            calls=[]
            def image_tool(*args):
                calls.append(args)
                if args[1]=='create':
                    stage=Path(args[args.index('-srcfolder')+1])
                    self.assertTrue((stage/'Install or Update.command').is_file())
                    self.assertTrue((stage/'Applications').is_symlink())
                    Path(args[-1]).write_bytes(b'new verified image')
            with patch.object(build_app,'ROOT',root), patch.object(build_app,'validate_app_launch'):
                release=build_app.package_dmg(app,output,runner=image_tool)
            self.assertEqual(output.read_bytes(),b'new verified image')
            self.assertIn('1.0.0-test1234',release.name)
            self.assertEqual(calls[-1][1],'verify')


class StartupGateTests(unittest.TestCase):
    def test_silent_exit_is_rejected_even_with_zero_exit_code(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temporary:
            app=Path(temporary)/'app.app';make_app(app)
            def closed(*args,**kwargs):return SimpleNamespace(returncode=0,stdout='',stderr='')
            with self.assertRaisesRegex(RuntimeError,'closed without confirming'):
                build_app.validate_app_launch(app,runner=closed)

    def test_real_ui_confirmation_is_required(self):
        import json
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temporary:
            app=Path(temporary)/'app.app';make_app(app)
            def launched(command,**kwargs):
                Path(command[-1]).write_text(json.dumps({'tabs':['AI & delivery','Results'],'version':'1.0.0','build_id':'test1234'}))
                return SimpleNamespace(returncode=0,stdout='',stderr='')
            build_app.validate_app_launch(app,runner=launched)

    def test_swedish_ui_confirmation_is_accepted(self):
        import json
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary) / 'app.app'
            make_app(app)
            def launched(command, **kwargs):
                Path(command[-1]).write_text(json.dumps({'tabs': ['AI och e-post', 'Resultat'], 'version': '1.0.0', 'build_id': 'test1234'}))
                return SimpleNamespace(returncode=0, stdout='', stderr='')
            build_app.validate_app_launch(app, runner=launched)

    def test_failed_startup_preserves_previous_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'build').mkdir()
            app=root/'app.app';make_app(app)
            output=root/'release.dmg';output.write_bytes(b'working image')
            with patch.object(build_app,'ROOT',root),patch.object(build_app,'validate_app_launch',side_effect=RuntimeError('missing ttkbootstrap')),self.assertRaisesRegex(RuntimeError,'ttkbootstrap'):
                build_app.package_dmg(app,output,runner=lambda *args:None)
            self.assertEqual(output.read_bytes(),b'working image')

    def test_shadowing_theme_module_is_rejected_before_build(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        def spec(name):return SimpleNamespace(submodule_search_locations=None if name=='ttkbootstrap' else [],origin='/project/ttkbootstrap.py')
        with patch.object(build_app.importlib.util,'find_spec',side_effect=spec),patch.object(build_app.subprocess,'run') as run,self.assertRaisesRegex(ValueError,'not its required package'):
            build_app.check_build_environment()
        run.assert_not_called()
