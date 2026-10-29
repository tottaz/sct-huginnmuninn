"""Run a disposable, offline UI with sample news for documentation screenshots."""
import json
from pathlib import Path
import sys
import tempfile
import tkinter as tk
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config_ui
from news_history import archive_report
from email_report import render_report

temporary = tempfile.TemporaryDirectory(prefix='huginn-docs-')
directory = Path(temporary.name)
settings = json.loads((config_ui.ROOT / 'config.example.json').read_text())
settings['deployment']['directory'] = str(directory)
config_path = directory / 'config.json'
config_path.write_text(json.dumps(settings))
config_ui.CONFIG = config_path
articles = [
    {'title': 'City expands its electric bus network', 'url': 'https://example.com/electric-buses',
     'source': 'Sample News · demonstration', 'status': 'article',
     'lead': 'A new route will connect more neighbourhoods with the city centre.',
     'text': 'Sample article: the city plans to add electric buses and expand evening services. Timetables will be published before the launch.',
     'analysis': '## Main findings\n- **More connections:** The new route would improve access to jobs and services.\n- **What remains unclear:** The final timetable and fares have not been announced.'},
    {'title': 'Rail services resume after disruption', 'url': 'https://example.com/rail-update',
     'source': 'Sample News · demonstration', 'status': 'blocked', 'reason': 'HTTP 429; original article not read.',
     'lead': '', 'text': '', 'analysis_origin': 'related_coverage',
     'analysis': 'Summary from related coverage\n\nOther public reporting says rail services are gradually resuming. Details remain incomplete. [1]\n\nSources:\n1. https://example.org/transport'},
    {'title': 'Community library opens a new reading room', 'url': 'https://example.com/library',
     'source': 'Sample News · demonstration', 'status': 'article', 'lead': 'The new space includes study desks and a children’s area.',
     'text': 'Sample article for the documentation.', 'analysis': 'The new reading room offers more space for study and community activities.'}]
archive_report(directory, articles, '2026-10-29T09:00:00+00:00')
_, html = render_report(articles)
(Path(__file__).parent / 'email-layout.html').write_text(html)
root = tk.Tk()
editor = config_ui.Editor(root)
for index, article in enumerate(articles):
    editor.upsert_result({'id': str(index), 'phase': 'complete', 'article': article})
editor.tabs.select(editor.history_page)
root.mainloop()
