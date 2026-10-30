"""Deploy a version independently of the editor and keep recoverable backups."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ASSETS = Path(__file__).resolve().parent
FROZEN = getattr(sys, 'frozen', False)
RUNNER_NAME = 'news-runner.exe' if sys.platform == 'win32' else 'news-runner'
DEFAULT_DIRECTORY = Path.home() / 'Dev' / 'sct-live-scripts' if sys.platform == 'darwin' else Path.home() / 'HuginnMuninn'
SCRIPT_NAME = 'sct_daily_news_analysis.py'
BACKUP_DIRECTORY = '.huginnmuninn-backups'


def deployment_directory(config):
    directory = Path(config.get('deployment', {}).get('directory', str(DEFAULT_DIRECTORY))).expanduser()
    if any(char in str(directory) for char in ('\n', '\r')):
        raise ValueError('Deployment directory cannot contain line breaks.')
    if not directory.is_absolute():
        raise ValueError('Deployment directory must be an absolute path.')
    return directory


def bundled_runner():
    path = ASSETS / RUNNER_NAME if FROZEN else ASSETS / 'dist' / RUNNER_NAME
    return path if path.is_file() else None


def atomic_write(path, content, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def deploy(config):
    """Copy script, dedicated config, and optional standalone runtime; return backup."""
    directory = deployment_directory(config)
    source = ASSETS / 'daily_news_analysis.py'
    compile(source.read_text(), str(source), 'exec')
    runner = bundled_runner()
    if FROZEN and runner is None:
        raise RuntimeError('The application is missing its bundled analysis runtime. Rebuild the app.')
    if runner is None:
        subprocess.run([sys.executable, '-c', 'import requests, bs4'], check=True, capture_output=True, timeout=30)
    # A dedicated config avoids touching config-sct.json used by other live scripts.
    files = {SCRIPT_NAME: (source.read_bytes(), 0o600),
             'smtp_settings.py': ((ASSETS / 'smtp_settings.py').read_bytes(), 0o600),
             'email_report.py': ((ASSETS / 'email_report.py').read_bytes(), 0o600),
             'result_formatting.py': ((ASSETS / 'result_formatting.py').read_bytes(), 0o600),
             'article_settings.py': ((ASSETS / 'article_settings.py').read_bytes(), 0o600),
             'run_events.py': ((ASSETS / 'run_events.py').read_bytes(), 0o600),
             'analysis_prompt.py': ((ASSETS / 'analysis_prompt.py').read_bytes(), 0o600),
             'news_scraper.py': ((ASSETS / 'news_scraper.py').read_bytes(), 0o600),
             'related_coverage.py': ((ASSETS / 'related_coverage.py').read_bytes(), 0o600),
             'ui_language.py': ((ASSETS / 'ui_language.py').read_bytes(), 0o600),
             'news_history.py': ((ASSETS / 'news_history.py').read_bytes(), 0o600),
             'huginnmuninn-config.json': ((json.dumps(config, indent=2) + '\n').encode(), 0o600)}
    command = [str(directory / RUNNER_NAME)] if runner else [sys.executable, '-u', str(directory / SCRIPT_NAME)]
    if runner:
        files[RUNNER_NAME] = (runner.read_bytes(), 0o700)
    manifest = {'command': command, 'script': SCRIPT_NAME, 'deployed_at': datetime.now(timezone.utc).isoformat()}
    files['huginnmuninn-deployment.json'] = ((json.dumps(manifest, indent=2) + '\n').encode(), 0o600)
    directory.mkdir(parents=True, exist_ok=True)
    keep_backups = config.get('deployment', {}).get('backups', True)
    if not isinstance(keep_backups, bool):
        raise ValueError('Deployment backups must be enabled or disabled.')
    backup = None
    previous = {}
    for name in files:
        target = directory / name
        previous[name] = (target.read_bytes(), target.stat().st_mode & 0o777) if target.exists() else None
    if keep_backups and any(value is not None for value in previous.values()):
        backup = directory / BACKUP_DIRECTORY / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup.mkdir(parents=True, mode=0o700)
        for name, old in previous.items():
            if old is None:
                continue
            target = directory / name
            shutil.copy2(target, backup / name)
            os.chmod(backup / name, 0o600)
    try:
        for name, (content, mode) in files.items():
            atomic_write(directory / name, content, mode)
    except Exception:
        rollback(directory, previous)
        raise
    return directory, backup, previous, command


def list_backups(config):
    """Return saved deployments, newest first, with their file count and size."""
    root = deployment_directory(config) / BACKUP_DIRECTORY
    if not root.is_dir():
        return []
    versions = []
    for path in root.iterdir():
        if not path.is_dir():
            continue
        files = [item for item in path.iterdir() if item.is_file()]
        versions.append({'name': path.name, 'path': path, 'files': len(files),
                         'size': sum(item.stat().st_size for item in files)})
    return sorted(versions, key=lambda item: item['name'], reverse=True)


def delete_backups(config, names):
    """Delete named backup versions after ensuring every target is a direct child."""
    root = deployment_directory(config) / BACKUP_DIRECTORY
    deleted = []
    for name in names:
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError('Invalid backup version.')
        target = root / name
        if target.is_dir():
            shutil.rmtree(target)
            deleted.append(name)
    if root.is_dir() and not any(root.iterdir()):
        root.rmdir()
    return deleted


def rollback(directory, previous):
    for name, old in previous.items():
        if old is None:
            (directory / name).unlink(missing_ok=True)
        else:
            atomic_write(directory / name, *old)


def sync_deployed_config(config):
    directory = deployment_directory(config)
    if (directory / 'huginnmuninn-deployment.json').is_file():
        atomic_write(directory / 'huginnmuninn-config.json', (json.dumps(config, indent=2) + '\n').encode())


def deployed_command(config):
    directory = deployment_directory(config)
    manifest = directory / 'huginnmuninn-deployment.json'
    if not manifest.is_file():
        raise ValueError('Deploy this version before running it.')
    return json.loads(manifest.read_text())['command']
