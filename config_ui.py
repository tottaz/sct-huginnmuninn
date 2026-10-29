"""Launch with python3 config_ui.py (requires Tkinter)."""
from app_version import version_label, build_info, support_summary
from mac_installer import install_dialog
from ui_launcher import ensure_ui_runtime

if __name__ == '__main__':
    ensure_ui_runtime(__file__)

import json
import queue
import os
import signal
import time
import webbrowser
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
import ttkbootstrap as ttk
from copy import deepcopy
from run_events import parse_event
from email_report import render_report
from article_settings import article_limit, DEFAULT_ARTICLE_LIMIT
from result_formatting import markdown_spans
from news_scraper import NewsScraper
from analysis_prompt import DEFAULT_ANALYSIS_PROMPT, get_analysis_prompt
from related_coverage import DEFAULT_MODEL
from news_history import search_history, get_article, delete_entries
from deployment import atomic_write, DEFAULT_DIRECTORY, deploy, deployed_command, deployment_directory, list_backups, delete_backups
from config_manager import CONFIG, DATA_DIRECTORY, ROOT, DEFAULT_SITES, save_config, validate, read_crontab, update_cron, list_ollama_models


class Editor:
    def __init__(self, root):
        self.root = root
        self.process = None
        self.run_id = 0
        self.run_started = None
        self.stopping = False
        self.preview_active = False
        self.preview_cancel = threading.Event()
        self.results = {}
        self.result_rows = {}
        self.row_keys = {}
        self.events = queue.Queue()
        root.title('Huginn & Muninn — Settings')
        root.geometry('1120x860')
        root.minsize(940, 740)
        self.style = ttk.Style(theme='darkly')
        self.style.configure('TButton', padding=(12, 8))
        self.style.configure('Treeview', rowheight=38)
        self.style.configure('Treeview.Heading', font=('', 11, 'bold'), padding=(8, 10))
        self.style.configure('TNotebook.Tab', padding=(14, 10))
        self.theme = tk.StringVar(value='Dark')
        self.original = {}
        self.fields = {}
        self.secret_controls = {}
        shell = ttk.Frame(root, padding=24)
        shell.pack(fill='both', expand=True)
        header = ttk.Frame(shell)
        header.pack(fill='x', pady=(0, 18))
        brand = ttk.Frame(header)
        brand.pack(side='left')
        ttk.Label(brand, text='HUGINN & MUNINN', font=('', 23, 'bold')).pack(anchor='w')
        ttk.Label(brand, text='Your daily perspective on the world', bootstyle='secondary').pack(anchor='w', pady=(4, 0))
        ttk.Label(brand, text=version_label(), font=('', 11, 'bold'), bootstyle='info').pack(anchor='w', pady=(3, 0))
        appearance = ttk.Frame(header)
        appearance.pack(side='right')
        ttk.Button(appearance, text='Copy support info', command=self.copy_support_info, bootstyle='info-outline').pack(side='right', padx=(12, 0))
        ttk.Label(appearance, text='Appearance', bootstyle='secondary').pack(side='left', padx=8)
        theme_picker = ttk.Combobox(appearance, textvariable=self.theme, values=['Dark', 'Light'], state='readonly', width=9)
        theme_picker.pack(side='left')
        theme_picker.bind('<<ComboboxSelected>>', self.change_theme)
        bar = ttk.Frame(shell)
        bar.pack(fill='x', pady=(0, 18))
        for label, command, style in [('Save settings', self.save, 'success'), ('Run now', self.run, 'primary'), ('Stop run', self.stop, 'danger-outline')]:
            button = ttk.Button(bar, text=label, command=command, bootstyle=style)
            button.pack(side='left', padx=(0, 8))
            if label == 'Run now':
                self.run_button = button
            elif label == 'Stop run':
                self.stop_button = button
                button.configure(state='disabled')
        ttk.Button(bar, text='Import settings', command=self.import_settings, bootstyle='secondary-outline').pack(side='right', padx=(8, 0))
        ttk.Button(bar, text='Reload', command=self.reload, bootstyle='secondary-outline').pack(side='right')
        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill='both', expand=True)
        ai_page = ttk.Frame(self.tabs, padding=20)
        sources_page = ttk.Frame(self.tabs, padding=20)
        schedule_page = ttk.Frame(self.tabs, padding=20)
        prompt_page = ttk.Frame(self.tabs, padding=20)
        self.tabs.add(ai_page, text='AI & delivery')
        self.tabs.add(prompt_page, text='Analysis prompt')
        self.tabs.add(sources_page, text='News sources')
        self.tabs.add(schedule_page, text='Schedule & deployment')
        self.results_page = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(self.results_page, text='Results')
        self.history_page = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(self.history_page, text='News history')
        history_header = ttk.Frame(self.history_page)
        history_header.pack(fill='x', pady=(0, 12))
        self.history_query = tk.StringVar()
        ttk.Label(history_header, text='Search saved news').pack(side='left', padx=(0, 10))
        search = ttk.Entry(history_header, textvariable=self.history_query)
        search.pack(side='left', fill='x', expand=True)
        search.bind('<Return>', lambda event: self.refresh_history())
        ttk.Button(history_header, text='Search / refresh', command=self.refresh_history, bootstyle='primary').pack(side='left', padx=8)
        history_list = ttk.Frame(self.history_page)
        history_list.pack(fill='both', expand=True)
        self.history_table = ttk.Treeview(history_list, columns=('title', 'date', 'url'), show='headings', selectmode='extended')
        for key, label, width in [('title', 'HEADLINE', 430), ('date', 'SCAN DATE (LOCAL)', 180), ('url', 'ARTICLE URL', 270)]:
            self.history_table.heading(key, text=label)
            self.history_table.column(key, width=width)
        scroll = ttk.Scrollbar(history_list, command=self.history_table.yview)
        self.history_table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.history_table.pack(fill='both', expand=True)
        self.history_table.bind('<Double-1>', lambda event: self.view_history())
        history_actions = ttk.Frame(self.history_page)
        history_actions.pack(fill='x', pady=12)
        ttk.Button(history_actions, text='View selected', command=self.view_history, bootstyle='info-outline').pack(side='left')
        ttk.Button(history_actions, text='Delete selected', command=self.delete_history, bootstyle='danger-outline').pack(side='left', padx=8)
        self.history_status = tk.StringVar(value='Refresh to load saved news from the deployment folder.')
        ttk.Label(self.history_page, textvariable=self.history_status, bootstyle='secondary').pack(anchor='w')
        self.tabs.bind('<<NotebookTabChanged>>', self.history_tab_changed)
        result_header = ttk.Frame(self.results_page)
        result_header.pack(fill='x', pady=(0, 10))
        self.results_summary = tk.StringVar(value='No results yet. Start a run or load the last report.')
        ttk.Label(result_header, textvariable=self.results_summary, bootstyle='info', wraplength=360).pack(side='left')
        ttk.Button(result_header, text='Preview email', command=self.preview_email, bootstyle='info-outline').pack(side='right', padx=(8, 0))
        ttk.Button(result_header, text='Load last report', command=self.load_last_report, bootstyle='secondary-outline').pack(side='right')
        self.follow_results = tk.BooleanVar(value=True)
        ttk.Checkbutton(result_header, text='Follow latest', variable=self.follow_results, bootstyle='success-round-toggle').pack(side='right', padx=12)
        email_actions = ttk.Frame(self.results_page)
        email_actions.pack(fill='x', pady=(0, 10))
        self.resend_button = ttk.Button(email_actions, text='Send saved report', command=lambda: self.run(resend_report=True), bootstyle='success-outline')
        self.resend_button.pack(side='left')
        ttk.Label(email_actions, text='Retry Gmail delivery without scraping or AI.', bootstyle='secondary').pack(side='left', padx=12)
        result_split = ttk.Panedwindow(self.results_page, orient='horizontal')
        result_split.pack(fill='both', expand=True)
        result_list = ttk.Frame(result_split)
        result_detail = ttk.Frame(result_split)
        result_split.add(result_list, weight=2)
        result_split.add(result_detail, weight=3)
        self.result_table = ttk.Treeview(result_list, columns=('title', 'state'), show='headings', selectmode='browse', height=6)
        self.result_table.heading('title', text='ARTICLE')
        self.result_table.heading('state', text='PROGRESS')
        self.result_table.column('title', width=240, minwidth=120)
        self.result_table.column('state', width=110, stretch=False)
        result_scroll = ttk.Scrollbar(result_list, command=self.result_table.yview)
        self.result_table.configure(yscrollcommand=result_scroll.set)
        result_scroll.pack(side='right', fill='y')
        self.result_table.pack(fill='both', expand=True)
        self.result_table.bind('<<TreeviewSelect>>', self.show_result)
        self.result_text = tk.Text(result_detail, state='disabled', wrap='word', relief='flat', borderwidth=0, padx=16, pady=14, font=('', 12))
        detail_scroll = ttk.Scrollbar(result_detail, command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=detail_scroll.set)
        detail_scroll.pack(side='right', fill='y')
        self.result_text.pack(fill='both', expand=True)

        ai_page.columnconfigure(0, weight=3)
        ai_page.columnconfigure(1, weight=2)
        ai_page.rowconfigure(0, weight=1)
        settings = ttk.Labelframe(ai_page, text='  Analysis engine  ', padding=16, bootstyle='primary')
        settings.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        delivery = ttk.Labelframe(ai_page, text='  Email delivery  ', padding=16, bootstyle='success')
        delivery.grid(row=0, column=1, sticky='nsew')
        for card in (settings, delivery):
            card.columnconfigure(1, weight=1)
        self.provider = tk.StringVar(value='Ollama')
        ttk.Label(settings, text='AI provider').grid(row=0, column=0, sticky='w', pady=9, padx=(0, 10))
        ttk.Combobox(settings, textvariable=self.provider, values=['Ollama', 'OpenAI'], state='readonly', width=20).grid(row=0, column=1, columnspan=2, sticky='ew')
        self.add_field(settings, 'ollama_base_url', 'Ollama server', 1)
        ttk.Label(settings, text='Ollama model').grid(row=2, column=0, sticky='w', pady=9, padx=(0, 10))
        self.model = tk.StringVar()
        self.model_picker = ttk.Combobox(settings, textvariable=self.model, width=20)
        self.model_picker.grid(row=2, column=1, columnspan=2, sticky='ew')
        self.refresh_button = ttk.Button(settings, text='Refresh installed models', command=self.refresh_models, bootstyle='info-outline')
        self.refresh_button.grid(row=3, column=1, columnspan=2, sticky='w', pady=(4, 8))
        self.add_field(settings, 'openai_model', 'OpenAI model', 4)
        self.add_field(settings, 'openai_api_key', 'OpenAI API key', 5, secret=True)
        self.model_status = tk.StringVar(value='Refresh to list installed models.')
        ttk.Label(settings, textvariable=self.model_status, bootstyle='secondary', wraplength=410).grid(row=6, column=0, columnspan=3, sticky='w', pady=(12, 0))
        self.add_field(delivery, 'email', 'Email', 0)
        self.add_field(delivery, 'app_password', 'App password', 1, secret=True)
        self.add_field(delivery, 'articles_per_site', 'Articles per site', 2)
        self.search_related_coverage = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings, text='Search related coverage when articles cannot be read', variable=self.search_related_coverage,
                        bootstyle='success-round-toggle').grid(row=7, column=0, columnspan=3, sticky='w', pady=(12, 4))
        self.add_field(settings, 'gemini_api_key', 'Gemini API key', 8, secret=True)
        self.add_field(settings, 'gemini_search_model', 'Search model', 9)
        ttk.Label(settings, text='Uses Google Search via Gemini. May incur API charges. Sends the headline, URL and public lead to Google.',
                  wraplength=440, bootstyle='secondary').grid(row=10, column=0, columnspan=3, sticky='w')
        ttk.Label(delivery, text='Use a Gmail app password.\n\nRun now saves and deploys your settings, then performs AI requests and sends the results by email.', wraplength=290, bootstyle='secondary', justify='left').grid(row=3, column=0, columnspan=3, sticky='nw', pady=(20, 0))
        ttk.Label(prompt_page, text='Shape the analysis', font=('', 16, 'bold')).pack(anchor='w')
        ttk.Label(prompt_page, text='These instructions are used for each article by both OpenAI and Ollama. Article text is supplied separately.', bootstyle='secondary', wraplength=900).pack(anchor='w', pady=(4, 14))
        prompt_frame = ttk.Frame(prompt_page)
        prompt_frame.pack(fill='both', expand=True)
        self.prompt_editor = tk.Text(prompt_frame, height=10, wrap='word', undo=True, relief='flat', borderwidth=0, padx=16, pady=14, font=('', 12))
        prompt_scroll = ttk.Scrollbar(prompt_frame, command=self.prompt_editor.yview)
        self.prompt_editor.configure(yscrollcommand=prompt_scroll.set)
        prompt_scroll.pack(side='right', fill='y')
        self.prompt_editor.pack(fill='both', expand=True)
        prompt_actions = ttk.Frame(prompt_page)
        prompt_actions.pack(fill='x', pady=(12, 0))
        ttk.Button(prompt_actions, text='Restore default prompt', command=self.restore_prompt, bootstyle='secondary-outline').pack(side='left')
        ttk.Label(prompt_actions, text='Save settings to use your changes in future runs.', bootstyle='secondary').pack(side='left', padx=14)
        ttk.Label(sources_page, text='Build your news desk', font=('', 16, 'bold')).pack(anchor='w')
        ttk.Label(sources_page, text='Add a URL. Feeds and article links are discovered automatically.', bootstyle='secondary').pack(anchor='w', pady=(4, 14))
        self.source_count = tk.StringVar()
        ttk.Label(sources_page, textvariable=self.source_count, bootstyle='info').pack(anchor='w', pady=(0, 8))
        table_frame = ttk.Frame(sources_page)
        table_frame.pack(fill='both', expand=True)
        self.sites = []
        self.site_table = ttk.Treeview(table_frame, columns=('url', 'selector', 'limit', 'enabled'), show='headings', height=5, selectmode='browse', bootstyle='primary')
        for key, title in [('url', 'NEWS SOURCE'), ('selector', 'SELECTOR OVERRIDE'), ('limit', 'ARTICLES'), ('enabled', 'STATUS')]:
            self.site_table.heading(key, text=title)
        self.site_table.column('url', width=460, minwidth=180)
        self.site_table.column('selector', width=240, minwidth=100)
        self.site_table.column('limit', width=90, stretch=False, anchor='center')
        self.site_table.column('enabled', width=100, stretch=False, anchor='center')
        scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=self.site_table.yview)
        self.site_table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.site_table.pack(fill='both', expand=True)
        self.site_table.bind('<Double-1>', lambda event: self.edit_site())
        self.site_table.bind('<ButtonPress-1>', self.start_site_drag)
        self.site_table.bind('<B1-Motion>', self.drag_site)
        self.site_table.bind('<ButtonRelease-1>', self.drop_site)
        self.site_table.bind('<Alt-Up>', lambda event: self.move_selected_site(-1))
        self.site_table.bind('<Alt-Down>', lambda event: self.move_selected_site(1))
        ttk.Label(sources_page, text='Drag a source onto another row to reorder. Alt+↑/↓ also works. Save settings to keep the order; reports follow this order.', bootstyle='secondary', wraplength=900).pack(anchor='w', pady=(8, 0))
        actions = ttk.Frame(sources_page)
        actions.pack(fill='x', pady=(14, 0))
        for label, command, style in [('Add site', self.add_site, 'success'), ('Edit site', self.edit_site, 'secondary-outline'), ('Delete site', self.delete_site, 'danger-outline'), ('Test site (no AI/email)', self.preview_site, 'info-outline')]:
            button = ttk.Button(actions, text=label, command=command, bootstyle=style)
            button.pack(side='left', padx=(0, 8))
            if command == self.preview_site:
                self.test_button = button
        ttk.Label(schedule_page, text='Let the ravens fly on schedule', font=('', 16, 'bold')).pack(anchor='w')
        ttk.Label(schedule_page, text='Deploy a version and manage its automatic runs from one place.', bootstyle='secondary').pack(anchor='w', pady=(4, 18))
        schedule = ttk.Labelframe(schedule_page, text='  Local deployment  ', padding=18, bootstyle='primary')
        schedule.pack(fill='x')
        schedule.columnconfigure(1, weight=1)
        self.add_field(schedule, 'deployment_directory', 'Deployment folder', 0)
        ttk.Button(schedule, text='Browse', command=self.choose_deployment, bootstyle='secondary-outline').grid(row=0, column=3, padx=(8, 0))
        self.expression = tk.StringVar(value='0 10,19 * * *')
        self.deployment_backups = tk.BooleanVar(value=True)
        ttk.Label(schedule, text='Cron expression').grid(row=1, column=0, sticky='w', padx=(0, 10), pady=12)
        ttk.Entry(schedule, textvariable=self.expression).grid(row=1, column=1, columnspan=2, sticky='ew')
        ttk.Label(schedule, text='0 10,19 * * *  →  Every day at 10:00 and 19:00 (system timezone)', bootstyle='secondary').grid(row=2, column=0, columnspan=4, sticky='w', pady=(0, 12))
        schedule_actions = ttk.Frame(schedule)
        ttk.Checkbutton(schedule, text='Create a backup before replacing deployed files', variable=self.deployment_backups,
                        bootstyle='success-round-toggle').grid(row=3, column=0, columnspan=4, sticky='w', pady=(0, 12))
        schedule_actions.grid(row=4, column=0, columnspan=4, sticky='w')
        for label, command, style in [('Deploy version', self.deploy_version, 'primary-outline'), ('Deploy + update cron', self.install, 'success'), ('Backups…', self.manage_backups, 'info-outline'), ('Remove schedule', self.remove, 'danger-outline'), ('Show crontab', self.show_cron, 'secondary-outline')]:
            button = ttk.Button(schedule_actions, text=label, command=command, bootstyle=style)
            button.pack(side='left', padx=(0, 8))
            if sys.platform == 'win32' and command in (self.install, self.remove, self.show_cron):
                button.configure(state='disabled')
        ttk.Label(schedule_page, text='Backup history is optional and can be viewed or deleted here. Failed deployments are still rolled back safely.\nOn Windows, deploy here and configure automatic runs in Task Scheduler.', bootstyle='secondary', justify='left', wraplength=880).pack(anchor='w', pady=18)
        activity_header = ttk.Frame(shell)
        activity_header.pack(fill='x', pady=(18, 8))
        self.run_status = tk.StringVar(value='Ready')
        self.run_elapsed = tk.StringVar(value='')
        self.run_progress = ttk.Progressbar(activity_header, mode='indeterminate', length=70, bootstyle='success')
        self.run_progress.pack(side='left', padx=(0, 10))
        ttk.Label(activity_header, textvariable=self.run_status, bootstyle='info', wraplength=700).pack(side='left')
        ttk.Label(activity_header, textvariable=self.run_elapsed, bootstyle='secondary').pack(side='right', padx=12)
        ttk.Button(activity_header, text='Clear', command=self.clear_output, bootstyle='secondary-link').pack(side='right')
        output_frame = ttk.Frame(shell)
        output_frame.pack(fill='x')
        self.output = tk.Text(output_frame, height=7, state='disabled', wrap='word', relief='flat', borderwidth=0, padx=14, pady=12, font=('Menlo' if sys.platform == 'darwin' else 'Consolas', 11))
        output_scroll = ttk.Scrollbar(output_frame, command=self.output.yview)
        self.output.configure(yscrollcommand=output_scroll.set)
        output_scroll.pack(side='right', fill='y')
        self.output.pack(fill='x', expand=True)
        self.apply_theme()
        self.reload()
        root.after(100, self.poll)
        root.after(1000, self.update_run_clock)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def copy_support_info(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(support_summary())
        self.root.update_idletasks()
        self.log('Support info copied. ' + version_label())

    def add_field(self, parent, key, label, row, secret=False):
        self.fields[key] = tk.StringVar()
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky='w', pady=10, padx=(0, 10))
        entry = (ttk.Spinbox(parent, textvariable=self.fields[key], from_=1, to=100, width=8) if key == 'articles_per_site'
                 else ttk.Entry(parent, textvariable=self.fields[key], show='•' if secret else '', width=18))
        entry.grid(row=row, column=1, columnspan=1 if secret else 2, sticky='ew')
        if secret:
            visible = tk.BooleanVar(value=False)
            toggle = ttk.Checkbutton(parent, text='Show', variable=visible, bootstyle='success-round-toggle',
                                     command=lambda: entry.configure(show='' if visible.get() else '•'))
            toggle.grid(row=row, column=2, padx=(8, 0))
            self.secret_controls[key] = (entry, toggle, visible)

    def apply_theme(self):
        self.style.theme_use('flatly' if self.theme.get() == 'Light' else 'darkly')
        for text in (self.output, self.prompt_editor, self.result_text):
            text.configure(background=self.style.colors.inputbg, foreground=self.style.colors.inputfg,
                           insertbackground=self.style.colors.fg, selectbackground=self.style.colors.primary)
        self.configure_result_styles()

    def configure_result_styles(self):
        text = self.result_text
        text.tag_configure('title', font=('', 18, 'bold'), spacing3=12)
        text.tag_configure('section', font=('', 13, 'bold'), spacing1=16, spacing3=8)
        text.tag_configure('heading', font=('', 13, 'bold'), spacing1=12, spacing3=6)
        text.tag_configure('metadata', foreground=self.style.colors.secondary, spacing3=4)
        text.tag_configure('body', spacing3=6)
        text.tag_configure('strong', font=('', 12, 'bold'))
        text.tag_configure('emphasis', font=('', 12, 'italic'))
        text.tag_configure('list', lmargin1=10, lmargin2=28, spacing3=6)
        mono = 'Menlo' if sys.platform == 'darwin' else 'Consolas'
        text.tag_configure('code', font=(mono, 11), background=self.style.colors.bg)
        text.tag_configure('codeblock', font=(mono, 11), background=self.style.colors.bg, lmargin1=12, lmargin2=12, spacing3=3)
        text.tag_configure('link', foreground=self.style.colors.info)

    def clear_results(self):
        self.results.clear()
        self.result_rows.clear()
        self.row_keys.clear()
        self.result_table.delete(*self.result_table.get_children())
        self.set_result_text('Select an article to see its lead, analysis, and extracted text.')
        self.results_summary.set('Waiting for articles…')

    def history_directory(self):
        return deployment_directory({'deployment': {'directory': self.fields['deployment_directory'].get().strip()}})

    def history_tab_changed(self, event=None):
        if self.tabs.select() == str(self.history_page):
            self.refresh_history()

    def refresh_history(self):
        def action():
            from datetime import datetime
            directory = self.history_directory()
            rows = search_history(directory, self.history_query.get())
            self.history_table.delete(*self.history_table.get_children())
            self.loaded_history_directory = directory
            for entry_id, scanned_at, title, url in rows:
                date = datetime.fromisoformat(scanned_at).astimezone().strftime('%Y-%m-%d %H:%M:%S')
                self.history_table.insert('', 'end', iid=str(entry_id), values=(title, date, url))
            self.history_status.set(f'{len(rows)} matching entries · {directory / "news-history.sqlite3"}')
        self.attempt(action)

    def view_history(self):
        selected = self.history_table.selection()
        if not selected:
            return
        def action():
            article = get_article(self.loaded_history_directory, int(selected[0]))
            dialog = tk.Toplevel(self.root)
            dialog.title(article.get('title') or 'Saved news')
            dialog.geometry('850x650')
            text = tk.Text(dialog, wrap='word', padx=20, pady=20)
            scrollbar = ttk.Scrollbar(dialog, command=text.yview)
            text.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side='right', fill='y')
            text.pack(fill='both', expand=True)
            sections = [article.get('title', ''), article.get('url', ''),
                        'Status: ' + article.get('status', ''), article.get('reason', ''),
                        'Lead\n' + article.get('lead', ''), 'Analysis\n' + article.get('analysis', ''),
                        'Article text\n' + article.get('text', '')]
            if article.get('analysis_error'):
                sections.append('Analysis failed: ' + article['analysis_error'])
            text.insert('1.0', '\n\n'.join(sections))
            text.configure(state='disabled')
        self.attempt(action)

    def delete_history(self):
        selected = self.history_table.selection()
        if not selected:
            return
        if messagebox.askyesno('Delete saved news', f'Delete {len(selected)} selected history entries? This cannot be undone.'):
            def action():
                delete_entries(self.loaded_history_directory, selected)
                self.log(f'Deleted {len(selected)} saved news entries permanently. Last report and sent emails are kept.')
                self.refresh_history()
            self.attempt(action)

    def set_result_text(self, text):
        self.result_text.configure(state='normal')
        self.result_text.delete('1.0', 'end')
        self.result_text.insert('1.0', text)
        self.result_text.configure(state='disabled')

    def upsert_result(self, event):
        key, article, phase = event['id'], event['article'], event.get('phase', 'extracted')
        self.results[key] = {'article': dict(article), 'phase': phase}
        labels = {'reading': 'Reading', 'analyzing': 'Analyzing', 'complete': 'Analyzed',
                  'failed': 'AI failed', 'interrupted': 'Interrupted', 'skipped': 'Skipped', 'extracted': 'Extracted'}
        title = article.get('title') or article.get('url') or key
        values = (title, labels.get(phase, phase))
        if key in self.result_rows:
            row = self.result_rows[key]
            self.result_table.item(row, values=values)
        else:
            row = self.result_table.insert('', 'end', values=values)
            self.result_rows[key] = row
            self.row_keys[row] = key
        if self.follow_results.get() or not self.result_table.selection():
            self.result_table.selection_set(row)
            self.result_table.see(row)
        if self.result_table.selection() == (row,):
            self.show_result()
        phases = [item['phase'] for item in self.results.values()]
        self.results_summary.set(f'{len(phases)} entries · {phases.count("complete")} analyzed · {phases.count("extracted")} extracted · {phases.count("skipped")} skipped · {phases.count("failed") + phases.count("interrupted")} failed')
        if phase in ('reading', 'analyzing') and not self.stopping:
            self.run_status.set(f'{labels[phase]}: {title[:95]}')
        elif phase == 'complete':
            self.log(f'Analysis ready: {title}')

    def show_result(self, event=None):
        selected = self.result_table.selection()
        if not selected:
            return
        item = self.results[self.row_keys[selected[0]]]
        article, phase = item['article'], item['phase']
        analysis = article.get('analysis')
        if not analysis:
            analysis = article.get('analysis_error') or {
                'reading': 'Fetching the article…', 'analyzing': 'Waiting for the model to return the analysis…',
                'skipped': 'No AI analysis: ' + article.get('reason', 'Not enough readable article text.'),
                'extracted': 'Extraction only; no analysis was requested.'}.get(phase, 'No analysis returned.')
        text = self.result_text
        text.configure(state='normal')
        text.delete('1.0', 'end')
        text.insert('end', (article.get('title') or 'Reading article…') + '\n', 'title')
        text.insert('end', article.get('url', '') + '\n', 'metadata')
        status = article.get('status', 'reading').replace('_', ' ').capitalize()
        text.insert('end', f"{status}  ·  {article.get('source', '')}\n", 'metadata')
        if article.get('reason'):
            text.insert('end', article['reason'] + '\n', 'metadata')
        for heading, value, markdown in [('Lead paragraph', article.get('lead') or 'Not available yet.', False),
                                          ('Analysis', analysis, True),
                                          ('Article text', article.get('text') or 'No readable article text was available.', False)]:
            text.insert('end', heading + '\n', 'section')
            if markdown:
                for content, tags in markdown_spans(value):
                    text.insert('end', content, tags)
            else:
                text.insert('end', value + '\n', 'body')
        text.configure(state='disabled')

    def preview_email(self):
        if not self.results:
            messagebox.showinfo('No entries yet', 'Run an analysis, test a site, or load the last report first.')
            return
        def action():
            articles = [item['article'] for item in self.results.values()]
            _, html = render_report(articles)
            path = DATA_DIRECTORY / 'email-preview.html'
            atomic_write(path, html.encode('utf-8'))
            webbrowser.open(path.as_uri())
            self.log('Email layout opened in your browser. Preview does not send an email.')
        self.attempt(action)

    def load_last_report(self):
        if getattr(self, 'preview_active', False) or (self.process and self.process.poll() is None):
            self.tabs.select(self.results_page)
            self.log('A run is in progress. Its live entries are shown in Results.')
            return
        def action():
            config = {'deployment': {'directory': self.fields['deployment_directory'].get().strip()}}
            path = deployment_directory(config) / 'news-results.json'
            if not path.is_file():
                raise ValueError('No saved report exists in the deployment folder yet. Finish an analysis run first.')
            report = json.loads(path.read_text())
            articles = report.get('articles')
            if not isinstance(articles, list) or any(not isinstance(item, dict) for item in articles):
                raise ValueError('The last report has an invalid article list.')
            self.clear_results()
            for index, article in enumerate(articles):
                phase = 'failed' if article.get('analysis_error') else ('complete' if article.get('analysis') else 'extracted' if article.get('status') == 'article' else 'skipped')
                self.upsert_result({'id': f'report:{index}', 'article': article, 'phase': phase})
            if not articles:
                self.results_summary.set('The last report contains no articles.')
            self.tabs.select(self.results_page)
            self.log(f'Loaded {len(articles)} entries from {path}.')
            return True
        return self.attempt(action)

    def set_running(self, running):
        self.run_button.configure(state='disabled' if running else 'normal')
        self.test_button.configure(state='disabled' if running else 'normal')
        self.resend_button.configure(state='disabled' if running else 'normal')
        self.stop_button.configure(state='normal' if running else 'disabled')
        if running:
            self.run_progress.start(15)
        else:
            self.run_progress.stop()

    def update_run_clock(self):
        if self.run_started is not None:
            elapsed = int(time.monotonic() - self.run_started)
            self.run_elapsed.set(f'{elapsed // 60:02d}:{elapsed % 60:02d} elapsed')
        self.root.after(1000, self.update_run_clock)

    def restore_prompt(self):
        self.prompt_editor.delete('1.0', 'end')
        self.prompt_editor.insert('1.0', DEFAULT_ANALYSIS_PROMPT)
        self.log('Default prompt restored in the editor. Save settings to keep it.')

    def change_theme(self, event=None):
        self.apply_theme()

    def choose_deployment(self):
        directory = filedialog.askdirectory(title='Choose deployment folder')
        if directory:
            self.fields['deployment_directory'].set(directory)

    def clear_output(self):
        self.output.configure(state='normal')
        self.output.delete('1.0', 'end')
        self.output.configure(state='disabled')

    def log(self, text):
        self.output.configure(state='normal')
        self.output.insert('end', text + '\n')
        self.output.see('end')
        self.output.configure(state='disabled')

    def attempt(self, function):
        try:
            return function()
        except Exception as error:
            messagebox.showerror('Could not complete action', str(error))

    def data(self):
        data = deepcopy(self.original)
        for key, variable in self.fields.items():
            if key != 'deployment_directory':
                data[key] = ''.join(variable.get().split()) if key == 'app_password' else variable.get().strip()
        try:
            data['articles_per_site'] = int(data['articles_per_site'])
        except ValueError:
            raise ValueError('Articles per site must be a whole number.')
        if 'deployment_directory' in self.fields:
            data.setdefault('deployment', {})['directory'] = self.fields['deployment_directory'].get().strip()
        if hasattr(self, 'deployment_backups'):
            data.setdefault('deployment', {})['backups'] = self.deployment_backups.get()
        data['use_openai'] = self.provider.get() == 'OpenAI'
        if hasattr(self, 'search_related_coverage'):
            data['search_related_coverage'] = self.search_related_coverage.get()
        data['ollama_model'] = self.model.get().strip()
        if not data['ollama_model']:
            raise ValueError('Select or enter an Ollama model.')
        if hasattr(self, 'prompt_editor'):
            data['analysis_prompt'] = self.prompt_editor.get('1.0', 'end-1c')
        data['news_sites'] = deepcopy(self.sites)
        data.setdefault('schedule', {})['expression'] = self.expression.get()
        if hasattr(self, 'theme'):
            data.setdefault('appearance', {})['theme'] = 'flatly' if self.theme.get() == 'Light' else 'darkly'
        return validate(data)

    def display(self, data):
        self.original = deepcopy(data)
        self.prompt_editor.delete('1.0', 'end')
        self.prompt_editor.insert('1.0', get_analysis_prompt(data))
        self.prompt_editor.edit_reset()
        if hasattr(self, 'theme'):
            self.theme.set('Light' if data.get('appearance', {}).get('theme') == 'flatly' else 'Dark')
            self.apply_theme()
        defaults = dict(openai_model='gpt-4', articles_per_site=DEFAULT_ARTICLE_LIMIT, gemini_search_model=DEFAULT_MODEL)
        if hasattr(self, 'search_related_coverage'):
            self.search_related_coverage.set(data.get('search_related_coverage', False))
        for key, variable in self.fields.items():
            variable.set(data.get('deployment', {}).get('directory', str(DEFAULT_DIRECTORY)) if key == 'deployment_directory' else data.get(key, defaults.get(key, '')))
        self.provider.set('OpenAI' if data.get('use_openai', False) else 'Ollama')
        self.model.set(data.get('ollama_model', 'llama3.2:latest'))
        if hasattr(self, 'deployment_backups'):
            self.deployment_backups.set(data.get('deployment', {}).get('backups', True))
        self.sites = [deepcopy(site) if isinstance(site, dict) else {'url': site, 'selector': '', 'enabled': True}
                      for site in data.get('news_sites', DEFAULT_SITES)]
        self.show_sites()

    def show_sites(self):
        self.site_table.delete(*self.site_table.get_children())
        self.source_count.set(f'{len(self.sites)} sources · {sum(site.get("enabled", True) for site in self.sites)} enabled')
        for index, site in enumerate(self.sites):
            self.site_table.insert('', 'end', iid=str(index), values=(site['url'], site.get('selector', ''), site.get('articles_per_site', 'Default'), 'Enabled' if site.get('enabled', True) else 'Paused'))

    def move_site(self, origin, target):
        if not (0 <= origin < len(self.sites) and 0 <= target < len(self.sites)):
            return
        if origin != target:
            self.sites.insert(target, self.sites.pop(origin))
            self.show_sites()
        row = str(target)
        self.site_table.selection_set(row)
        self.site_table.focus(row)
        self.site_table.see(row)

    def move_selected_site(self, offset):
        selected = self.site_table.selection()
        if selected:
            origin = int(selected[0])
            self.move_site(origin, origin + offset)
        return 'break'

    def start_site_drag(self, event):
        self.site_drag_row = (self.site_table.identify_row(event.y)
                              if self.site_table.identify_region(event.x, event.y) == 'cell' else '')

    def drag_site(self, event):
        if not getattr(self, 'site_drag_row', ''):
            return
        self.site_table.configure(cursor='hand2')
        if event.y < 40:
            self.site_table.yview_scroll(-1, 'units')
        elif event.y > self.site_table.winfo_height() - 20:
            self.site_table.yview_scroll(1, 'units')
        row = self.site_table.identify_row(event.y)
        if row:
            self.site_table.selection_set(row)

    def drop_site(self, event):
        origin = getattr(self, 'site_drag_row', '')
        self.site_drag_row = ''
        self.site_table.configure(cursor='')
        target = self.site_table.identify_row(event.y)
        if origin and target:
            self.move_site(int(origin), int(target))

    def import_settings(self):
        path = filedialog.askopenfilename(title='Import settings', filetypes=[('Config files', '*.json')])
        if path:
            def action():
                with open(path) as stream:
                    data = validate(json.load(stream))
                self.expression.set(data.get('schedule', {}).get('expression', '0 10,19 * * *'))
                self.display(data)
                self.log('Settings imported. Save config to keep them.')
            self.attempt(action)

    def reload(self):
        def action():
            path = CONFIG if CONFIG.exists() else ROOT / 'config.example.json'
            data = json.loads(path.read_text())
            data.setdefault('news_sites', [{'url': url, 'enabled': True, 'selector': ''} for url in DEFAULT_SITES])
            self.expression.set(data.get('schedule', {}).get('expression', '0 10,19 * * *'))
            self.display(data)
        self.attempt(action)

    def refresh_models(self):
        def action():
            base_url = self.fields['ollama_base_url'].get().strip()
            self.refresh_button.configure(state='disabled')
            self.model_picker.configure(values=())
            self.model_status.set('Loading models…')
            def fetch():
                try:
                    self.events.put(('models', base_url, list_ollama_models(base_url), None))
                except Exception as error:
                    self.events.put(('models', base_url, [], str(error)))
            threading.Thread(target=fetch, daemon=True).start()
        self.attempt(action)

    def receive_models(self, base_url, names, error):
        self.refresh_button.configure(state='normal')
        if self.fields['ollama_base_url'].get().strip() != base_url:
            self.model_status.set('Server changed. Refresh models again.')
            return
        if error:
            self.model_status.set('Could not load models. See output.')
            self.log('Ollama: ' + error + '. Check that Ollama is running and the URL is correct.')
            return
        self.model_picker.configure(values=names)
        selected = self.model.get()
        self.model.set(selected)
        self.model_status.set(f'{len(names)} models available.' if names else 'No models installed. Use ollama pull <model>.')
        if names and selected not in names:
            self.model_status.set('Configured model unavailable. Select an installed model.')

    def save(self):
        def action():
            save_config(self.data())
            self.log('Saved config.json.')
            return True
        return self.attempt(action)

    def change_site(self, mode):
        selected = self.site_table.selection()
        if mode != 'add' and not selected:
            messagebox.showinfo('Select a site', 'Select a site in the table first.')
            return
        index = int(selected[0]) if selected else None
        if mode == 'delete':
            self.sites.pop(index)
            self.show_sites()
            return
        old = deepcopy(self.sites[index]) if mode == 'edit' else {'url': '', 'selector': '', 'enabled': True}
        dialog = tk.Toplevel(self.root)
        dialog.title('Edit site' if mode == 'edit' else 'Add site')
        dialog.transient(self.root)
        dialog.grab_set()
        url = tk.StringVar(value=old['url'])
        selector = tk.StringVar(value=old.get('selector', ''))
        feed = tk.StringVar(value=old.get('feed_url', ''))
        enabled = tk.BooleanVar(value=old.get('enabled', True))
        site_limit = tk.StringVar(value=old.get('articles_per_site', ''))
        for row, (label, variable) in enumerate([('Site URL', url), ('CSS selector (optional)', selector), ('RSS/Atom URL (optional)', feed)]):
            ttk.Label(dialog, text=label).grid(row=row, column=0, padx=10, pady=8, sticky='w')
            ttk.Entry(dialog, textvariable=variable, width=55).grid(row=row, column=1, padx=10)
        ttk.Label(dialog, text='Articles (blank = default)').grid(row=3, column=0, padx=10, pady=8, sticky='w')
        ttk.Spinbox(dialog, textvariable=site_limit, from_=1, to=100, width=10).grid(row=3, column=1, padx=10, sticky='w')
        ttk.Checkbutton(dialog, text='Enabled', variable=enabled).grid(row=4, column=1, sticky='w')
        ttk.Label(dialog, text='Just enter a site URL. Feed and selector override automatic discovery.').grid(row=5, column=0, columnspan=2, padx=10, pady=8)
        def apply():
            def action():
                site = dict(old, url=url.get().strip(), selector=selector.get().strip(), feed_url=feed.get().strip(), enabled=enabled.get())
                if site_limit.get().strip():
                    try:
                        site['articles_per_site'] = int(site_limit.get())
                    except ValueError:
                        raise ValueError('Articles per site must be a whole number from 1 to 100.')
                else:
                    site.pop('articles_per_site', None)
                # Validate the site independently of unfinished settings fields.
                validate(dict(email='placeholder', app_password='placeholder', use_openai=False,
                              ollama_base_url='http://localhost:11434', news_sites=[site]))
                if mode == 'edit':
                    self.sites[index] = site
                else:
                    self.sites.append(site)
                self.show_sites()
                dialog.destroy()
            self.attempt(action)
        ttk.Button(dialog, text='Apply', command=apply).grid(row=6, column=1, sticky='e', padx=10, pady=10)
        ttk.Button(dialog, text='Cancel', command=dialog.destroy).grid(row=6, column=0, padx=10, pady=10)

    def add_site(self): self.change_site('add')
    def edit_site(self): self.change_site('edit')
    def delete_site(self): self.change_site('delete')

    def preview_site(self):
        if self.preview_active or (self.process and self.process.poll() is None):
            self.tabs.select(self.results_page)
            self.log('A run or site test is already in progress. Use Stop run before starting another.')
            return
        selected = self.site_table.selection()
        if not selected:
            messagebox.showinfo('Select a site', 'Select a site to test first.')
            return
        try:
            configured = int(self.fields['articles_per_site'].get())
            source = deepcopy(self.sites[int(selected[0])])
            limit = article_limit({'articles_per_site': configured}, source)
        except (ValueError, TypeError) as error:
            messagebox.showerror('Invalid article limit', str(error))
            return
        self.run_id += 1
        run_id = self.run_id
        self.preview_active = True
        self.preview_cancel = threading.Event()
        cancel = self.preview_cancel
        self.stopping = False
        self.clear_results()
        self.tabs.select(self.results_page)
        self.run_started = time.monotonic()
        self.run_status.set(f'Testing site · up to {limit} articles…')
        self.set_running(True)
        self.log(f"Testing {source['url']} · limit {limit} · extraction only, no AI or email.")
        def send(event):
            self.events.put(('run-event', run_id, event))
        def fetch():
            scraper = NewsScraper(log=lambda text: self.events.put(('run-log', run_id, text)))
            code = 0
            try:
                links = scraper.discover(source['url'], selector=source.get('selector'), feed_url=source.get('feed_url'), limit=limit)
                if not links:
                    self.events.put(('run-log', run_id, 'No article links found. Try a feed URL or CSS selector.'))
                for url in links[:limit]:
                    if cancel.is_set():
                        break
                    send({'type': 'article', 'id': url, 'phase': 'reading', 'article': {'url': url, 'source': source['url']}})
                    article = scraper.article(url)
                    if cancel.is_set():
                        break
                    data = dict(article.to_dict(), source=source['url'], analysis='')
                    send({'type': 'article', 'id': url, 'phase': 'extracted' if article.status == 'article' else 'skipped', 'article': data})
            except Exception as error:
                code = 1
                self.events.put(('run-log', run_id, f'Site test failed: {error}'))
            finally:
                self.events.put(('run-finished', run_id, code))
        threading.Thread(target=fetch, daemon=True).start()

    def deploy_version(self):
        if not self.save():
            return
        def action():
            directory, backup, _, _ = deploy(self.data())
            detail = f' Backup: {backup}.' if backup else ' No backup created.'
            self.log(f'Deployed version to {directory}.{detail} Schedule unchanged.')
        self.attempt(action)

    def install(self):
        def action():
            data = self.data()
            data.setdefault('schedule', {})['expression'] = self.expression.get()
            save_config(data)
            self.display(data)
            directory, backup = update_cron(self.expression.get(), data)
            detail = f' Backup: {backup}.' if backup else ' No backup created.'
            self.log(f'Deployed and scheduled in {directory}.{detail} Output: {directory / "news-analysis.log"}')
        self.attempt(action)

    def manage_backups(self):
        def action():
            config = {'deployment': {
                'directory': self.fields['deployment_directory'].get().strip(),
                'backups': self.deployment_backups.get(),
            }}
            dialog = tk.Toplevel(self.root)
            dialog.title('Deployment backups')
            dialog.geometry('760x430')
            dialog.transient(self.root)
            dialog.grab_set()
            ttk.Label(dialog, text=str(deployment_directory(config)), bootstyle='secondary', wraplength=720).pack(anchor='w', padx=18, pady=(18, 10))
            table = ttk.Treeview(dialog, columns=('version', 'files', 'size'), show='headings', selectmode='extended')
            for key, label, width in [('version', 'UTC VERSION', 360), ('files', 'FILES', 90), ('size', 'SIZE', 130)]:
                table.heading(key, text=label)
                table.column(key, width=width, stretch=key == 'version')
            table.pack(fill='both', expand=True, padx=18)
            status = tk.StringVar()
            ttk.Label(dialog, textvariable=status, bootstyle='secondary').pack(anchor='w', padx=18, pady=8)
            def refresh():
                table.delete(*table.get_children())
                versions = list_backups(config)
                for item in versions:
                    table.insert('', 'end', iid=item['name'], values=(item['name'], item['files'], self.format_size(item['size'])))
                status.set(f'{len(versions)} saved version' + ('' if len(versions) == 1 else 's'))
            def remove(selected_only):
                names = list(table.selection()) if selected_only else list(table.get_children())
                if not names:
                    messagebox.showinfo('No backups selected', 'Select one or more backup versions first.', parent=dialog)
                    return
                label = f'{len(names)} selected backup version' if selected_only else 'all backup versions'
                if not messagebox.askyesno('Delete backups', f'Delete {label}{"s" if selected_only and len(names) != 1 else ""}? This cannot be undone.', parent=dialog):
                    return
                deleted = delete_backups(config, names)
                self.log(f'Deleted {len(deleted)} deployment backup version(s).')
                refresh()
            actions = ttk.Frame(dialog)
            actions.pack(fill='x', padx=18, pady=(2, 18))
            ttk.Button(actions, text='Delete selected', command=lambda: remove(True), bootstyle='danger-outline').pack(side='left')
            ttk.Button(actions, text='Delete all', command=lambda: remove(False), bootstyle='danger').pack(side='left', padx=8)
            ttk.Button(actions, text='Close', command=dialog.destroy, bootstyle='secondary-outline').pack(side='right')
            refresh()
        self.attempt(action)

    @staticmethod
    def format_size(size):
        value = float(size)
        for unit in ('B', 'KB', 'MB', 'GB'):
            if value < 1024 or unit == 'GB':
                return f'{value:.0f} {unit}' if unit == 'B' else f'{value:.1f} {unit}'
            value /= 1024

    def remove(self):
        self.attempt(lambda: (update_cron(), self.log('Managed cron schedule removed.')))

    def show_cron(self):
        self.attempt(lambda: self.log(read_crontab() or 'No crontab installed.'))

    def run(self, resend_report=False):
        if getattr(self, 'preview_active', False) or (self.process and self.process.poll() is None):
            self.tabs.select(self.results_page)
            self.log('Run in progress. Select an entry in Results to inspect it, or use Stop run.')
            return
        if not self.save():
            return
        def action():
            config = self.data()
            if resend_report and not self.load_last_report():
                return
            deploy(config)
            arguments = ['--events', '--resend-report'] if resend_report else ['--events']
            self.process = subprocess.Popen(deployed_command(config) + arguments, cwd=deployment_directory(config),
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                                            start_new_session=(os.name != 'nt'))
            self.run_id += 1
            run_id, process = self.run_id, self.process
            self.stopping = False
            if not resend_report:
                self.clear_results()
            self.tabs.select(self.results_page)
            self.run_started = time.monotonic()
            self.run_status.set('Sending saved report to Gmail…' if resend_report else 'Starting analysis…')
            self.set_running(True)
            def stream():
                try:
                    with process.stdout:
                        for line in process.stdout:
                            event = parse_event(line)
                            self.events.put(('run-event', run_id, event) if event else ('run-log', run_id, line.rstrip()))
                except Exception as error:
                    self.events.put(('run-log', run_id, f'Could not read analysis output: {error}'))
                finally:
                    self.events.put(('run-finished', run_id, process.wait()))
            threading.Thread(target=stream, daemon=True).start()
            self.log('Sending the saved report only. No scraping or AI requests.' if resend_report else 'Analysis started. Live entries and their analyses appear in Results.')
        self.attempt(action)

    def signal_process(self, process, force=False):
        if process.poll() is not None:
            return
        try:
            if os.name != 'nt':
                os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
            else:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=10)
        except ProcessLookupError:
            pass

    def stop(self):
        if self.preview_active:
            self.stopping = True
            self.preview_cancel.set()
            self.run_status.set('Stopping site test after the current request…')
            self.stop_button.configure(state='disabled')
            return
        if self.process and self.process.poll() is None:
            self.stopping = True
            self.run_status.set('Stopping analysis…')
            self.stop_button.configure(state='disabled')
            process = self.process
            self.signal_process(process)
            self.root.after(5000, lambda: self.signal_process(process, force=True))
            self.log('Stop requested. Entries received so far remain visible.')

    def handle_run_message(self, event):
        kind, run_id, payload = event
        if run_id != self.run_id:
            return
        if kind == 'run-log':
            self.log(payload)
        elif kind == 'run-event':
            if payload['type'] == 'article':
                self.upsert_result(payload)
            elif payload['type'] == 'progress':
                if not self.stopping:
                    self.run_status.set(payload.get('message', 'Running…'))
        elif kind == 'run-finished':
            was_preview = self.preview_active
            self.preview_active = False
            self.set_running(False)
            self.run_started = None
            status = 'Stopped' if self.stopping else ('Site test finished' if was_preview else 'Finished') if payload == 0 else 'Failed'
            # Entries awaiting a model response remain inspectable after cancellation.
            for key, item in list(self.results.items()):
                if item['phase'] in ('reading', 'analyzing'):
                    article = dict(item['article'], analysis_error='Run ended before this entry completed.')
                    self.upsert_result({'id': key, 'article': article, 'phase': 'interrupted'})
            if not self.results:
                self.results_summary.set('No articles were received. See activity messages for details.')
            display_status = f'{status} (exit {payload})' if payload and not self.stopping else status
            self.run_status.set(f'{display_status} · {self.results_summary.get()}')
            self.log(f'{display_status}.')

    def poll(self):
        # Bound each batch so a large report cannot starve redraws and Stop run.
        for _ in range(100):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if isinstance(event, tuple) and event[0] == 'models':
                self.receive_models(*event[1:])
            elif isinstance(event, tuple) and event[0].startswith('run-'):
                self.handle_run_message(event)
            else:
                self.log(event)
        self.root.after(100, self.poll)

    def close(self):
        self.preview_cancel.set()
        if self.process and self.process.poll() is None:
            self.signal_process(self.process, force=True)
        self.root.destroy()


if __name__ == '__main__':
    if '--install-app' in sys.argv:
        install_dialog()
        raise SystemExit(0)
    root = ttk.Window(themename='darkly', iconphoto=None)
    editor = Editor(root)
    if '--smoke-test' in sys.argv:
        root.update()
        from pathlib import Path
        Path(sys.argv[sys.argv.index('--smoke-test') + 1]).write_text(json.dumps({'version': build_info()['version'], 'build_id': build_info()['build_id'], 'title': root.title(), 'fields': list(editor.fields), 'sites': len(editor.sites), 'config_path': str(CONFIG), 'theme': editor.style.theme_use(), 'tabs': [editor.tabs.tab(tab, 'text') for tab in editor.tabs.tabs()]}))
        root.destroy()
    else:
        root.mainloop()
