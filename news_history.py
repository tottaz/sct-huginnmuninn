"""Local searchable archive of article snapshots, separate from deployment backups."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(directory / 'news-history.sqlite3', timeout=15)
    try:
        database.execute('CREATE TABLE IF NOT EXISTS articles (id INTEGER PRIMARY KEY, scanned_at TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL, article TEXT NOT NULL)')
        yield database
        database.commit()
    except Exception:
        database.rollback()
        raise
    finally:
        database.close()


def archive_report(directory, articles, scanned_at):
    with connect(directory) as database:
        database.executemany('INSERT INTO articles (scanned_at, title, url, article) VALUES (?, ?, ?, ?)',
                             [(scanned_at, item.get('title') or '(Title unavailable)', item.get('url', ''),
                               json.dumps(item, ensure_ascii=False)) for item in articles])


def search_history(directory, query=''):
    # Literal substring search, including headline, URL, extracted text and analysis.
    with connect(directory) as database:
        return database.execute('SELECT id, scanned_at, title, url FROM articles WHERE instr(lower(article), lower(?)) > 0 ORDER BY scanned_at DESC, id DESC', (query.strip(),)).fetchall()


def get_article(directory, entry_id):
    with connect(directory) as database:
        row = database.execute('SELECT article FROM articles WHERE id = ?', (entry_id,)).fetchone()
    if row is None:
        raise ValueError('This history entry no longer exists. Refresh the history.')
    return json.loads(row[0])


def delete_entries(directory, entry_ids):
    with connect(directory) as database:
        database.executemany('DELETE FROM articles WHERE id = ?', [(int(value),) for value in entry_ids])
    # Reclaim space after removing stored article bodies.
    with connect(directory) as database:
        database.execute('VACUUM')


def delete_all_entries(directory):
    """Clear the entire archive, independently of any UI search filter."""
    with connect(directory) as database:
        count = database.execute('SELECT count(*) FROM articles').fetchone()[0]
        database.execute('DELETE FROM articles')
    with connect(directory) as database:
        database.execute('VACUUM')
    return count
