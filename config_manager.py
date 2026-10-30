"""Configuration and isolated crontab management for the local editor."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from smtp_settings import settings as smtp_options
from ui_language import validate_language
from article_settings import article_limit
from analysis_prompt import get_analysis_prompt
from deployment import ASSETS, FROZEN, atomic_write, deploy, rollback, sync_deployed_config
from urllib.request import urlopen
from urllib.parse import urlparse

ROOT = ASSETS
if FROZEN:
    if sys.platform == 'darwin':
        DATA_DIRECTORY = Path.home() / 'Library' / 'Application Support' / 'HuginnMuninn'
    elif sys.platform == 'win32':
        DATA_DIRECTORY = Path(os.environ.get('APPDATA', str(Path.home()))) / 'HuginnMuninn'
    else:
        DATA_DIRECTORY = Path.home() / '.config' / 'HuginnMuninn'
else:
    DATA_DIRECTORY = ROOT
CONFIG = DATA_DIRECTORY / 'config.json'
BEGIN = '# BEGIN sct-huginnmuninn'
END = '# END sct-huginnmuninn'
LEGACY_SCRIPT = '/Users/tottazetterlund/Dev/sct-live-scripts/sct_daily_news_analysis.py'
DEFAULT_SITES = [
    'https://www.theguardian.com/world',
    'https://www.theguardian.com/world/europe-news',
    'https://www.aftonbladet.se', 'https://www.expressen.se',
    'https://www.epochtimes.se', 'https://www.svt.se/',
]


def validate(config):
    if not isinstance(config, dict):
        raise ValueError('Configuration must be a JSON object.')
    appearance = config.get('appearance', {})
    if not isinstance(appearance, dict):
        raise ValueError('appearance must be an object.')
    validate_language(appearance.get('language', 'en'))
    get_analysis_prompt(config)
    if not isinstance(config.get('search_related_coverage', False), bool):
        raise ValueError('search_related_coverage must be true or false.')
    for key in ('gemini_api_key', 'gemini_search_model'):
        if key in config and not isinstance(config[key], str):
            raise ValueError(f'{key} must be a string.')
    if config.get('search_related_coverage') and not config.get('gemini_api_key', '').strip():
        raise ValueError('A Gemini API key is required for related coverage searches.')
    for key in ('email', 'ollama_base_url'):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f'{key} must be a nonempty string.')
    smtp_options(config)
    article_limit(config)
    sites = config.get('news_sites', DEFAULT_SITES)
    if not isinstance(sites, list):
        raise ValueError('news_sites must be an array.')
    for site in sites:
        url = site.get('url') if isinstance(site, dict) else site
        if not isinstance(url, str) or urlparse(url).scheme not in ('http', 'https') or not urlparse(url).netloc:
            raise ValueError('Every site needs an http(s) URL.')
        if isinstance(site, dict):
            article_limit(config, site)
            if not isinstance(site.get('enabled', True), bool):
                raise ValueError('Site enabled must be true or false.')
            if not isinstance(site.get('selector', ''), str):
                raise ValueError('Site selector must be a string.')
            feed = site.get('feed_url', '')
            if not isinstance(feed, str) or (feed and (urlparse(feed).scheme not in ('http', 'https') or not urlparse(feed).netloc)):
                raise ValueError('Feed URL must be an http(s) URL or blank.')
    schedule = config.get('schedule', {})
    if not isinstance(schedule, dict):
        raise ValueError('schedule must be an object.')
    validate_cron(schedule.get('expression', '0 10,19 * * *'))
    deployment = config.get('deployment', {})
    if not isinstance(deployment, dict):
        raise ValueError('deployment must be an object.')
    if not isinstance(deployment.get('backups', True), bool):
        raise ValueError('deployment.backups must be true or false.')
    return config


def validate_cron(expression):
    if not isinstance(expression, str) or len(expression.split()) != 5:
        raise ValueError('Cron needs five fields: minute hour day month weekday.')
    for field, (low, high) in zip(expression.split(), [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]):
        for part in field.split(','):
            if not re.fullmatch(r'(\*|\d+(-\d+)?)(/\d+)?', part):
                raise ValueError('Use numeric cron fields, *, ranges, lists, and /steps.')
            base, _, step = part.partition('/')
            if step and not 1 <= int(step) <= high - low + 1:
                raise ValueError('Cron step is out of range.')
            if base != '*':
                values = [int(value) for value in base.split('-')]
                if any(not low <= value <= high for value in values) or values != sorted(values):
                    raise ValueError('Cron value or range is invalid.')
    return expression


def save_config(config):
    config = dict(config)
    for key in ('use_openai', 'openai_api_key', 'openai_model'):
        config.pop(key, None)
    if isinstance(config.get('app_password'), str):
        config['app_password'] = smtp_options(config)['password']
    validate(config)
    atomic_write(CONFIG, (json.dumps(config, indent=2) + '\n').encode())
    sync_deployed_config(config)


def read_crontab():
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=10)
    if result.returncode and 'no crontab for' not in result.stderr.lower():
        raise RuntimeError(result.stderr.strip() or 'Could not read crontab.')
    return result.stdout if result.returncode == 0 else ''


def cron_content(current, expression=None, command=None, directory=None, log_path=None):
    if current.count(BEGIN) != current.count(END) or current.count(BEGIN) > 1:
        raise ValueError('Managed cron markers are malformed; inspect crontab manually.')
    if BEGIN in current:
        start, finish = current.index(BEGIN), current.index(END) + len(END)
        if finish < start:
            raise ValueError('Managed cron markers are out of order.')
        current = current[:start] + current[finish:].lstrip('\n')
    # Migrate only direct invocations of the known legacy news script.
    kept = []
    for line in current.splitlines(keepends=True):
        try:
            tokens = shlex.split(line)
        except ValueError:
            tokens = []
        legacy = (len(tokens) >= 7 and not line.lstrip().startswith('#')
                  and Path(tokens[5]).name.startswith('python') and tokens[6] == LEGACY_SCRIPT)
        if not legacy:
            kept.append(line)
    current = ''.join(kept)
    if expression is not None:
        validate_cron(expression)
        # Cron treats percent specially, even inside shell quotes.
        quote = lambda value: shlex.quote(str(value)).replace('%', r'\%')
        directory = Path(directory or ROOT)
        command = command or [sys.executable, '-u', str(ROOT / 'daily_news_analysis.py')]
        command = f'cd {quote(directory)} && {" ".join(quote(part) for part in command)} >> {quote(log_path or directory / "news-analysis.log")} 2>&1' 
        current = current.rstrip('\n') + ('\n' if current else '')
        current += f'{BEGIN}\n{expression} {command}\n{END}\n'
    return current


def update_cron(expression=None, config=None):
    current = read_crontab()
    if expression is not None:
        validate_cron(expression)
        # Check markers before changing deployed files.
        cron_content(current)
        if config is None:
            raise ValueError('Configuration is required to deploy and install the schedule.')
        validate(config)
        directory, backup, previous, command = deploy(config)
        content = cron_content(current, expression, command, directory)
    else:
        content = cron_content(current)
    try:
        result = subprocess.run(['crontab', '-'], input=content, capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'Could not update crontab.')
    except Exception:
        if expression is not None:
            rollback(directory, previous)
        raise
    return (directory, backup) if expression is not None else None


def list_ollama_models(base_url):
    """List installed models using Ollama's native API, including /v1 configs."""
    base = base_url.strip().rstrip('/')
    if base.endswith('/v1'):
        base = base[:-3]
    parsed = urlparse(base)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError('Ollama base URL must be an http(s) server URL without query or fragment.')
    with urlopen(base + '/api/tags', timeout=10) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or not isinstance(payload.get('models'), list):
        raise ValueError('Ollama returned an invalid model list.')
    names = []
    for model in payload['models']:
        if not isinstance(model, dict) or not isinstance(model.get('name'), str) or not model['name'].strip():
            raise ValueError('Ollama returned an invalid model name.')
        names.append(model['name'])
    return sorted(set(names))
