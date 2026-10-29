"""Build versioned apps and publish a DMG only after creation and verification."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

from app_version import APP_ID, APP_NAME as NAME, VERSION
from release_version import reserve_version, version_parts

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'


def run(*args):
    subprocess.run(list(map(str, args)), cwd=ROOT, check=True)


def check_build_environment():
    """Check real imports, not just package metadata discovered by PyInstaller."""
    names = ('PyInstaller', 'ttkbootstrap', 'requests', 'bs4', 'openai')
    missing = [name for name in names if importlib.util.find_spec(name) is None]
    if missing:
        raise ValueError('Missing build dependencies: ' + ', '.join(missing) + '. Use .venv-build/bin/python or install requirements.txt and requirements-build.txt in the selected environment.')
    theme_spec = importlib.util.find_spec('ttkbootstrap')
    if theme_spec.submodule_search_locations is None:
        raise ValueError(f'ttkbootstrap resolves to a module, not its required package: {theme_spec.origin}. Remove a shadowing ttkbootstrap.py file or select the prepared project environment.')
    probe = """import json,sys,ttkbootstrap,PyInstaller,requests,bs4,openai,pydantic
from pydantic import BaseModel
class Check(BaseModel):
    value: str
assert Check(value='ok').value == 'ok'
if sys.version_info >= (3,14) and tuple(int(part) for part in pydantic.VERSION.split('.')[:2]) < (2,12):
    raise RuntimeError('Python 3.14 requires Pydantic 2.12 or newer; Pydantic V1 is unsupported.')
print(json.dumps({'python':sys.executable,'theme_package':ttkbootstrap.__file__,'pydantic':pydantic.VERSION}))
"""
    result = subprocess.run([sys.executable, '-c', probe], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Build dependency imports failed before packaging:\n' + (result.stderr or result.stdout)[-3000:])
    details = json.loads(result.stdout)
    print(f"Build Python: {details['python']}\nTheme package: {details['theme_package']}\nPydantic runtime: {details['pydantic']}", flush=True)
    return details


def validate_app_launch(app, runner=None):
    """Reject apps that exit silently or fail to create the actual desktop UI."""
    runner = runner or subprocess.run
    app = Path(app)
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    executable = app / 'Contents/MacOS' / info['CFBundleExecutable']
    with tempfile.TemporaryDirectory(prefix='huginn-launch-') as temporary:
        report = Path(temporary) / 'ui.json'
        environment = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT='1')
        try:
            result = runner([str(executable), '--smoke-test', str(report)], capture_output=True, text=True, timeout=30, env=environment)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError('The packaged app did not finish its startup check. Check for a settings error dialog; no DMG was published.') from error
        if result.returncode or not report.is_file():
            diagnostic = (result.stderr or result.stdout or 'App closed without confirming startup.')[-3000:]
            raise RuntimeError('Packaged app startup failed; no DMG was published:\n' + diagnostic)
        data = json.loads(report.read_text())
        if not isinstance(data.get('tabs'), list) or 'Results' not in data['tabs']:
            raise RuntimeError('Packaged app did not create the required UI; no DMG was published.')
        if data.get('version') != info.get('CFBundleShortVersionString') or data.get('build_id') != info.get('HuginnBuildID'):
            raise RuntimeError('Displayed version/build does not match the app bundle; rebuild before publishing a DMG.')
    print('Packaged UI startup check passed.', flush=True)


def package_dmg(app, output, runner=run):
    """Keep the previous release until the temporary image passes verification."""
    app, output = Path(app), Path(output)
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    runner('codesign', '--verify', '--deep', '--strict', app)
    validate_app_launch(app)
    version = info.get('CFBundleShortVersionString', VERSION)
    build_id = info.get('HuginnBuildID', 'legacy')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='huginn-dmg-', dir=ROOT / 'build') as temporary:
        stage = Path(temporary) / 'contents'
        stage.mkdir()
        shutil.copytree(app, stage / app.name, symlinks=True)
        (stage / 'Applications').symlink_to('/Applications')
        installer = stage / 'Install or Update.command'
        installer.write_text('#!/bin/bash\nset -eu\napp_dir="$(cd "$(dirname "$0")" && pwd)"\nexec "$app_dir/Huginn Muninn.app/Contents/MacOS/Huginn Muninn" --install-app\n')
        installer.chmod(0o755)
        (stage / 'Read Me First.txt').write_text(
            f'{NAME} {version} — build {build_id}\n\n'
            '1. Quit the installed app after finishing or stopping an active analysis.\n'
            '2. Double-click Install or Update.command and choose Applications.\n'
            '   Alternatively, drag Huginn Muninn.app to Applications and choose Replace.\n'
            '3. Open the copy in Applications, then eject this disk image.\n'
            '4. Use Deploy version in the app to update the scheduled worker too.\n\n'
            'Settings remain in ~/Library/Application Support/HuginnMuninn.\n'
            'The installer backs up the previous app in that folder under App Backups.\n'
            'If macOS blocks this local unsigned build, use System Settings > Privacy & Security > Open Anyway after attempting to open it.\n'
            'This build is ad-hoc signed, not Developer ID signed or notarized.\n')
        temporary_image = Path(temporary) / 'release.dmg'
        runner('hdiutil', 'create', '-volname', f'{NAME} {version} {build_id}', '-srcfolder', stage, '-format', 'UDZO', temporary_image)
        runner('hdiutil', 'verify', temporary_image)
        release = output.with_name(f'Huginn-Muninn-{version}-{build_id}.dmg')
        os.replace(temporary_image, release)
        alias = output.with_name('.' + output.name + '.' + uuid.uuid4().hex)
        try:
            os.link(release, alias)
            os.replace(alias, output)
        finally:
            alias.unlink(missing_ok=True)
        return release


def build(app_only=False, dmg_only=False, version=None):
    if version is not None:
        version_parts(version)
    os.environ['PYINSTALLER_CONFIG_DIR'] = str(ROOT / 'build' / 'pyinstaller-cache')
    DIST.mkdir(exist_ok=True)
    (ROOT / 'build').mkdir(exist_ok=True)
    if dmg_only:
        if version is not None:
            raise ValueError('--dmg-only keeps the built app version; use a full rebuild to change it.')
        return package_dmg(DIST / f'{NAME}.app', DIST / 'Huginn-Muninn.dmg')
    check_build_environment()
    version = reserve_version(ROOT, version)
    print(f'Reserved app version {version}.', flush=True)
    build_id = uuid.uuid4().hex[:8]
    build_info = ROOT / 'build' / 'build-info.json'
    build_info.write_text(json.dumps({'version': version, 'build_id': build_id}))
    suffix = '.exe' if sys.platform == 'win32' else ''
    icon = ROOT / 'assets' / ('app.ico' if suffix else 'app.icns')
    base = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--specpath', ROOT / 'build', '--log-level', 'WARN']
    for module in ['torch', 'tensorflow', 'transformers', 'pandas', 'scipy', 'numpy', 'matplotlib', 'IPython', 'jupyter', 'notebook', 'cv2', 'moviepy', 'sympy', 'pytest', 'sklearn']:
        base += ['--exclude-module', module]
    run(*base, '--onefile', '--name', 'news-runner', '--exclude-module', 'tkinter', ROOT / 'analysis_runner.py')
    command = [*base, '--windowed', '--onedir', '--name', NAME, '--icon', icon, '--collect-data', 'ttkbootstrap']
    if sys.platform == 'darwin':
        command += ['--osx-bundle-identifier', APP_ID]
    for name in ['daily_news_analysis.py', 'news_scraper.py', 'related_coverage.py', 'news_history.py', 'analysis_prompt.py', 'run_events.py', 'article_settings.py', 'email_report.py', 'result_formatting.py', 'config.example.json']:
        command += ['--add-data', f'{ROOT / name}{os.pathsep}.']
    command += ['--add-data', f'{build_info}{os.pathsep}.', '--add-data', f'{DIST / ("news-runner" + suffix)}{os.pathsep}.', ROOT / 'config_ui.py']
    run(*command)
    if sys.platform == 'darwin':
        app = DIST / f'{NAME}.app'
        plist = app / 'Contents' / 'Info.plist'
        info = plistlib.loads(plist.read_bytes())
        info.update(CFBundleIdentifier=APP_ID, CFBundleShortVersionString=version, CFBundleVersion=version, HuginnBuildID=build_id)
        plist.write_bytes(plistlib.dumps(info))
        run('codesign', '--force', '--sign', '-', app)
        run('codesign', '--verify', '--deep', '--strict', app)
        if not app_only:
            release = package_dmg(app, DIST / 'Huginn-Muninn.dmg')
            print(f'Built {release}')
        else:
            validate_app_launch(app)
            print(f'Built {app}. Create the image with: {sys.executable} build_app.py --dmg-only')
    elif sys.platform == 'win32':
        shutil.make_archive(str(DIST / 'Huginn-Muninn-Windows'), 'zip', DIST / NAME)
        print(f'Built {DIST / NAME / (NAME + suffix)} and Windows ZIP')
    else:
        print(f'Built {DIST / NAME}')


if __name__ == '__main__':
    from ui_launcher import ensure_ui_runtime
    if '--dmg-only' not in sys.argv:
        ensure_ui_runtime(__file__)
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--app-only', action='store_true', help='Build the app without creating a disk image.')
    modes.add_argument('--dmg-only', action='store_true', help='Package the already-built app; do not rebuild Python.')
    parser.add_argument('--version', default=None, help='Reserve a newer release version explicitly; otherwise increment the patch version automatically.')
    args = parser.parse_args()
    try:
        build(args.app_only, args.dmg_only, args.version)
    except Exception as error:
        print(f'Build failed: {error}\nThe last working DMG is preserved. If disk-image creation was blocked in Codex, run build_app.py --dmg-only in Terminal.', file=sys.stderr)
        raise SystemExit(1)
