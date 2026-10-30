"""Launch with python3 config_ui.py (requires Tkinter)."""
from smtp_settings import settings as smtp_options, test_connection as test_smtp_connection
from ui_language import LANGUAGES, translate
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
from news_history import search_history, get_article, delete_entries, delete_all_entries
from deployment import atomic_write, DEFAULT_DIRECTORY, deploy, deployed_command, deployment_directory, list_backups, delete_backups
from config_manager import CONFIG, DATA_DIRECTORY, ROOT, DEFAULT_SITES, save_config, validate, read_crontab, update_cron, list_ollama_models


class Editor:
    def __init__(self, root):
        self.root = root
        self.language = tk.StringVar(value="English")
        self.default_language = "en"
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
        root.title(self.tr('Huginn & Muninn — Settings'))
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
        ttk.Label(brand, text=self.tr('HUGINN & MUNINN'), font=('', 23, 'bold')).pack(anchor='w')
        ttk.Label(brand, text=self.tr('Your daily perspective on the world'), bootstyle='secondary').pack(anchor='w', pady=(4, 0))
        ttk.Label(brand, text=self.tr(version_label()), font=('', 11, 'bold'), bootstyle='info').pack(anchor='w', pady=(3, 0))
        appearance = ttk.Frame(header)
        appearance.pack(side='right')
        ttk.Button(appearance, text=self.tr('Copy support info'), command=self.copy_support_info, bootstyle='info-outline').pack(side='right', padx=(12, 0))
        ttk.Label(appearance, text=self.tr('Appearance'), bootstyle='secondary').pack(side='left', padx=8)
        self.theme_picker = theme_picker = ttk.Combobox(appearance, textvariable=self.theme, values=['Dark', 'Light'], state='readonly', width=9)
        theme_picker.pack(side='left')
        theme_picker.bind('<<ComboboxSelected>>', self.change_theme)
        language_bar = ttk.Frame(shell)
        language_bar.pack(fill='x', pady=(0, 12))
        ttk.Label(language_bar, text=self.tr('Language')).pack(side='left', padx=(0, 8))
        language_picker = ttk.Combobox(language_bar, textvariable=self.language, values=list(LANGUAGES), state='readonly', width=12)
        language_picker.pack(side='left')
        language_picker.bind('<<ComboboxSelected>>', self.change_language)
        ttk.Button(language_bar, text=self.tr('Use as default'), command=self.save_default_language, bootstyle='secondary-outline').pack(side='left', padx=8)
        self.language_status = tk.StringVar()
        ttk.Label(language_bar, textvariable=self.language_status, bootstyle='secondary').pack(side='left', padx=8)
        bar = ttk.Frame(shell)
        bar.pack(fill='x', pady=(0, 18))
        for label, command, style in [('Save settings', self.save, 'success'), ('Run now', self.run, 'primary'), ('Stop run', self.stop, 'danger-outline')]:
            button = ttk.Button(bar, text=self.tr(label), command=command, bootstyle=style)
            button.pack(side='left', padx=(0, 8))
            if label == 'Run now':
                self.run_button = button
            elif label == 'Stop run':
                self.stop_button = button
                button.configure(state='disabled')
        ttk.Button(bar, text=self.tr('Import settings'), command=self.import_settings, bootstyle='secondary-outline').pack(side='right', padx=(8, 0))
        ttk.Button(bar, text=self.tr('Reload'), command=self.reload, bootstyle='secondary-outline').pack(side='right')
        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill='both', expand=True)
        ai_page = ttk.Frame(self.tabs, padding=20)
        email_page = ttk.Frame(self.tabs, padding=20)
        sources_page = ttk.Frame(self.tabs, padding=20)
        schedule_page = ttk.Frame(self.tabs, padding=20)
        prompt_page = ttk.Frame(self.tabs, padding=20)
        self.tabs.add(ai_page, text=self.tr('Analysis engine'))
        self.tabs.add(email_page, text=self.tr('Email delivery'))
        self.tabs.add(prompt_page, text=self.tr('Analysis prompt'))
        self.tabs.add(sources_page, text=self.tr('News sources'))
        self.tabs.add(schedule_page, text=self.tr('Schedule & deployment'))
        self.results_page = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(self.results_page, text=self.tr('Results'))
        self.history_page = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(self.history_page, text=self.tr('News history'))
        history_header = ttk.Frame(self.history_page)
        history_header.pack(fill='x', pady=(0, 12))
        self.history_query = tk.StringVar()
        ttk.Label(history_header, text=self.tr('Search saved news')).pack(side='left', padx=(0, 10))
        search = ttk.Entry(history_header, textvariable=self.history_query)
        search.pack(side='left', fill='x', expand=True)
        search.bind('<Return>', lambda event: self.refresh_history())
        ttk.Button(history_header, text=self.tr('Search / refresh'), command=self.refresh_history, bootstyle='primary').pack(side='left', padx=8)
        history_list = ttk.Frame(self.history_page)
        history_list.pack(fill='both', expand=True)
        self.history_table = ttk.Treeview(history_list, columns=('title', 'date', 'url'), show='headings', selectmode='extended')
        for key, label, width in [('title', 'HEADLINE', 430), ('date', 'SCAN DATE (LOCAL)', 180), ('url', 'ARTICLE URL', 270)]:
            self.history_table.heading(key, text=self.tr(label))
            self.history_table.column(key, width=width)
        scroll = ttk.Scrollbar(history_list, command=self.history_table.yview)
        self.history_table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.history_table.pack(fill='both', expand=True)
        self.history_table.bind('<Double-1>', lambda event: self.view_history())
        history_actions = ttk.Frame(self.history_page)
        history_actions.pack(fill='x', pady=12)
        ttk.Button(history_actions, text=self.tr('View selected'), command=self.view_history, bootstyle='info-outline').pack(side='left')
        ttk.Button(history_actions, text=self.tr('Delete selected'), command=self.delete_history, bootstyle='danger-outline').pack(side='left', padx=8)
        ttk.Button(history_actions, text=self.tr('Select all'), command=self.select_all_history, bootstyle='secondary-outline').pack(side='left', padx=8)
        ttk.Button(history_actions, text=self.tr('Clear selection'), command=self.clear_history_selection, bootstyle='secondary-outline').pack(side='left')
        ttk.Button(history_actions, text=self.tr('Delete all'), command=self.delete_all_history, bootstyle='danger').pack(side='right')
        ttk.Label(self.history_page, text=self.tr('Use ⌘/Ctrl-click to select multiple entries, or Shift-click to select a range.'), bootstyle='secondary').pack(anchor='w', pady=(0, 6))
        self.history_table.bind('<<TreeviewSelect>>', self.update_history_status)
        self.history_table.bind('<Command-a>' if sys.platform == 'darwin' else '<Control-a>', self.select_all_history)
        self.history_status = tk.StringVar(value=self.tr('Refresh to load saved news from the deployment folder.'))
        ttk.Label(self.history_page, textvariable=self.history_status, bootstyle='secondary').pack(anchor='w')
        self.tabs.bind('<<NotebookTabChanged>>', self.history_tab_changed)
        result_header = ttk.Frame(self.results_page)
        result_header.pack(fill='x', pady=(0, 10))
        self.results_summary = tk.StringVar(value=self.tr('No results yet. Start a run or load the last report.'))
        ttk.Label(result_header, textvariable=self.results_summary, bootstyle='info', wraplength=360).pack(side='left')
        ttk.Button(result_header, text=self.tr('Preview email'), command=self.preview_email, bootstyle='info-outline').pack(side='right', padx=(8, 0))
        ttk.Button(result_header, text=self.tr('Load last report'), command=self.load_last_report, bootstyle='secondary-outline').pack(side='right')
        self.follow_results = tk.BooleanVar(value=True)
        ttk.Checkbutton(result_header, text=self.tr('Follow latest'), variable=self.follow_results, bootstyle='success-round-toggle').pack(side='right', padx=12)
        email_actions = ttk.Frame(self.results_page)
        email_actions.pack(fill='x', pady=(0, 10))
        self.resend_button = ttk.Button(email_actions, text=self.tr('Send saved report'), command=lambda: self.run(resend_report=True), bootstyle='success-outline')
        self.resend_button.pack(side='left')
        ttk.Label(email_actions, text=self.tr('Retry email delivery without scraping or AI.'), bootstyle='secondary').pack(side='left', padx=12)
        result_split = ttk.Panedwindow(self.results_page, orient='horizontal')
        result_split.pack(fill='both', expand=True)
        result_list = ttk.Frame(result_split)
        result_detail = ttk.Frame(result_split)
        result_split.add(result_list, weight=2)
        result_split.add(result_detail, weight=3)
        self.result_table = ttk.Treeview(result_list, columns=('title', 'state'), show='headings', selectmode='browse', height=6)
        self.result_table.heading('title', text=self.tr('ARTICLE'))
        self.result_table.heading('state', text=self.tr('PROGRESS'))
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

        ai_page.columnconfigure(0, weight=1)
        email_page.columnconfigure((0, 1), weight=1, uniform="email")
        email_page.rowconfigure(0, weight=1)
        ai_page.rowconfigure(0, weight=1)
        settings = ttk.Labelframe(ai_page, text=self.tr('  Analysis engine  '), padding=16, bootstyle='primary')
        settings.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        delivery = ttk.Labelframe(email_page, text=self.tr('  Email delivery  '), padding=16, bootstyle='success')
        delivery.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        smtp_card = ttk.Labelframe(email_page, text=self.tr('  SMTP connection  '), padding=16, bootstyle='info')
        smtp_card.grid(row=0, column=1, sticky='nsew')
        for card in (settings, delivery, smtp_card):
            card.columnconfigure(1, weight=1)
        ttk.Label(settings, text='Ollama', font=('', 14, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 8))
        self.add_field(settings, 'ollama_base_url', self.tr('Ollama server'), 1)
        ttk.Label(settings, text=self.tr('Ollama model')).grid(row=2, column=0, sticky='w', pady=9, padx=(0, 10))
        self.model = tk.StringVar()
        self.model_picker = ttk.Combobox(settings, textvariable=self.model, width=20)
        self.model_picker.grid(row=2, column=1, columnspan=2, sticky='ew')
        self.refresh_button = ttk.Button(settings, text=self.tr('Refresh installed models'), command=self.refresh_models, bootstyle='info-outline')
        self.refresh_button.grid(row=3, column=1, columnspan=2, sticky='w', pady=(4, 8))
        self.model_status = tk.StringVar(value=self.tr('Refresh to list installed models.'))
        ttk.Label(settings, textvariable=self.model_status, bootstyle='secondary', wraplength=410).grid(row=4, column=0, columnspan=3, sticky='w', pady=(12, 0))
        self.add_field(delivery, 'email', self.tr('Recipient email'), 0)
        self.add_field(delivery, 'smtp_sender', self.tr('Sender email (blank = recipient)'), 1)
        self.add_field(smtp_card, 'smtp_host', self.tr('SMTP server'), 0)
        self.add_field(smtp_card, 'smtp_port', self.tr('SMTP port'), 1)
        ttk.Label(smtp_card, text=self.tr('Encryption')).grid(row=2, column=0, sticky='w', pady=10)
        self.smtp_security = tk.StringVar(value='ssl')
        security_picker = ttk.Combobox(smtp_card, textvariable=self.smtp_security, values=['ssl', 'starttls', 'none'], state='readonly')
        security_picker.grid(row=2, column=1, columnspan=2, sticky='ew')
        security_picker.bind('<<ComboboxSelected>>', self.change_smtp_security)
        self.smtp_authenticate = tk.BooleanVar(value=True)
        ttk.Checkbutton(smtp_card, text=self.tr('Server requires authentication'), variable=self.smtp_authenticate, bootstyle='success-round-toggle').grid(row=3, column=0, columnspan=3, sticky='w', pady=8)
        self.add_field(delivery, 'smtp_username', self.tr('SMTP username (blank = recipient)'), 2)
        self.add_field(delivery, 'app_password', self.tr('Password / app password'), 3, secret=True)
        self.add_field(settings, 'articles_per_site', self.tr('Articles per site'), 9)
        self.search_related_coverage = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings, text=self.tr('Search related coverage when articles cannot be read'), variable=self.search_related_coverage,
                        bootstyle='success-round-toggle').grid(row=5, column=0, columnspan=3, sticky='w', pady=(12, 4))
        self.add_field(settings, 'gemini_api_key', self.tr('Gemini API key'), 6, secret=True)
        self.add_field(settings, 'gemini_search_model', self.tr('Search model'), 7)
        ttk.Label(settings, text=self.tr('Uses Google Search via Gemini. May incur API charges. Sends the headline, URL and public lead to Google.'),
                  wraplength=440, bootstyle='secondary').grid(row=8, column=0, columnspan=3, sticky='w')
        ttk.Label(email_page, text=self.tr('ssl = TLS from connection start; starttls = upgrade before sign-in; none = unencrypted. Use your email provider’s SMTP settings. Gmail defaults are preserved.'), wraplength=860, bootstyle='secondary', justify='left').grid(row=1, column=0, columnspan=2, sticky='w', pady=12)
        self.smtp_test_button = ttk.Button(email_page, text=self.tr('Test connection (no email)'), command=self.test_email_connection, bootstyle='info-outline')
        self.smtp_test_button.grid(row=2, column=0, columnspan=2, sticky='w')
        ttk.Label(prompt_page, text=self.tr('Shape the analysis'), font=('', 16, 'bold')).pack(anchor='w')
        ttk.Label(prompt_page, text=self.tr('These instructions are used for each article by Ollama. Article text is supplied separately.'), bootstyle='secondary', wraplength=900).pack(anchor='w', pady=(4, 14))
        prompt_frame = ttk.Frame(prompt_page)
        prompt_frame.pack(fill='both', expand=True)
        self.prompt_editor = tk.Text(prompt_frame, height=10, wrap='word', undo=True, relief='flat', borderwidth=0, padx=16, pady=14, font=('', 12))
        prompt_scroll = ttk.Scrollbar(prompt_frame, command=self.prompt_editor.yview)
        self.prompt_editor.configure(yscrollcommand=prompt_scroll.set)
        prompt_scroll.pack(side='right', fill='y')
        self.prompt_editor.pack(fill='both', expand=True)
        prompt_actions = ttk.Frame(prompt_page)
        prompt_actions.pack(fill='x', pady=(12, 0))
        ttk.Button(prompt_actions, text=self.tr('Restore default prompt'), command=self.restore_prompt, bootstyle='secondary-outline').pack(side='left')
        ttk.Label(prompt_actions, text=self.tr('Save settings to use your changes in future runs.'), bootstyle='secondary').pack(side='left', padx=14)
        ttk.Label(sources_page, text=self.tr('Build your news desk'), font=('', 16, 'bold')).pack(anchor='w')
        ttk.Label(sources_page, text=self.tr('Add a URL. Feeds and article links are discovered automatically.'), bootstyle='secondary').pack(anchor='w', pady=(4, 14))
        self.source_count = tk.StringVar()
        ttk.Label(sources_page, textvariable=self.source_count, bootstyle='info').pack(anchor='w', pady=(0, 8))
        table_frame = ttk.Frame(sources_page)
        table_frame.pack(fill='both', expand=True)
        self.sites = []
        self.site_table = ttk.Treeview(table_frame, columns=('url', 'selector', 'limit', 'enabled'), show='headings', height=5, selectmode='browse', bootstyle='primary')
        for key, title in [('url', 'NEWS SOURCE'), ('selector', 'SELECTOR OVERRIDE'), ('limit', 'ARTICLES'), ('enabled', 'STATUS')]:
            self.site_table.heading(key, text=self.tr(title))
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
        ttk.Label(sources_page, text=self.tr('Drag a source onto another row to reorder. Alt+↑/↓ also works. Save settings to keep the order; reports follow this order.'), bootstyle='secondary', wraplength=900).pack(anchor='w', pady=(8, 0))
        actions = ttk.Frame(sources_page)
        actions.pack(fill='x', pady=(14, 0))
        for label, command, style in [('Add site', self.add_site, 'success'), ('Edit site', self.edit_site, 'secondary-outline'), ('Delete site', self.delete_site, 'danger-outline'), ('Test site (no AI/email)', self.preview_site, 'info-outline')]:
            button = ttk.Button(actions, text=self.tr(label), command=command, bootstyle=style)
            button.pack(side='left', padx=(0, 8))
            if command == self.preview_site:
                self.test_button = button
        ttk.Label(schedule_page, text=self.tr('Let the ravens fly on schedule'), font=('', 16, 'bold')).pack(anchor='w')
        ttk.Label(schedule_page, text=self.tr('Deploy a version and manage its automatic runs from one place.'), bootstyle='secondary').pack(anchor='w', pady=(4, 18))
        schedule = ttk.Labelframe(schedule_page, text=self.tr('  Local deployment  '), padding=18, bootstyle='primary')
        schedule.pack(fill='x')
        schedule.columnconfigure(1, weight=1)
        self.add_field(schedule, 'deployment_directory', self.tr('Deployment folder'), 0)
        ttk.Button(schedule, text=self.tr('Browse'), command=self.choose_deployment, bootstyle='secondary-outline').grid(row=0, column=3, padx=(8, 0))
        self.expression = tk.StringVar(value='0 10,19 * * *')
        self.deployment_backups = tk.BooleanVar(value=True)
        ttk.Label(schedule, text=self.tr('Cron expression')).grid(row=1, column=0, sticky='w', padx=(0, 10), pady=12)
        ttk.Entry(schedule, textvariable=self.expression).grid(row=1, column=1, columnspan=2, sticky='ew')
        ttk.Label(schedule, text=self.tr('0 10,19 * * *  →  Every day at 10:00 and 19:00 (system timezone)'), bootstyle='secondary').grid(row=2, column=0, columnspan=4, sticky='w', pady=(0, 12))
        schedule_actions = ttk.Frame(schedule)
        ttk.Checkbutton(schedule, text=self.tr('Create a backup before replacing deployed files'), variable=self.deployment_backups,
                        bootstyle='success-round-toggle').grid(row=3, column=0, columnspan=4, sticky='w', pady=(0, 12))
        schedule_actions.grid(row=4, column=0, columnspan=4, sticky='w')
        for label, command, style in [('Deploy version', self.deploy_version, 'primary-outline'), ('Deploy + update cron', self.install, 'success'), ('Backups…', self.manage_backups, 'info-outline'), ('Remove schedule', self.remove, 'danger-outline'), ('Show crontab', self.show_cron, 'secondary-outline')]:
            button = ttk.Button(schedule_actions, text=self.tr(label), command=command, bootstyle=style)
            button.pack(side='left', padx=(0, 8))
            if sys.platform == 'win32' and command in (self.install, self.remove, self.show_cron):
                button.configure(state='disabled')
        ttk.Label(schedule_page, text=self.tr('Backup history is optional and can be viewed or deleted here. Failed deployments are still rolled back safely.\nOn Windows, deploy here and configure automatic runs in Task Scheduler.'), bootstyle='secondary', justify='left', wraplength=880).pack(anchor='w', pady=18)
        activity_header = ttk.Frame(shell)
        activity_header.pack(fill='x', pady=(18, 8))
        self.run_status = tk.StringVar(value=self.tr('Ready'))
        self.run_elapsed = tk.StringVar(value='')
        self.run_progress = ttk.Progressbar(activity_header, mode='indeterminate', length=70, bootstyle='success')
        self.run_progress.pack(side='left', padx=(0, 10))
        ttk.Label(activity_header, textvariable=self.run_status, bootstyle='info', wraplength=700).pack(side='left')
        ttk.Label(activity_header, textvariable=self.run_elapsed, bootstyle='secondary').pack(side='right', padx=12)
        ttk.Button(activity_header, text=self.tr('Clear'), command=self.clear_output, bootstyle='secondary-link').pack(side='right')
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

    def tr(self, text, **values):
        language = LANGUAGES.get(self.language.get(), 'en') if hasattr(self, 'language') else 'en'
        return translate(text, language, **values)

    def localize_widgets(self, widget):
        # Only presentation labels/headings are touched, never editable user values.
        if isinstance(widget, (ttk.Label, ttk.Button, ttk.Checkbutton, ttk.Labelframe)):
            variable = str(widget.cget('textvariable')) if 'textvariable' in widget.keys() else ''
            if variable:
                self.root.setvar(variable, self.tr(self.root.getvar(variable)))
            else:
                widget.configure(text=self.tr(widget.cget('text')))
        if isinstance(widget, ttk.Notebook):
            for tab in widget.tabs():
                widget.tab(tab, text=self.tr(widget.tab(tab, 'text')))
        if isinstance(widget, ttk.Treeview):
            for column in widget.cget('columns'):
                widget.heading(column, text=self.tr(widget.heading(column, 'text')))
        if isinstance(widget, tk.Toplevel):
            widget.title(self.tr(widget.title()))
        for child in widget.winfo_children():
            self.localize_widgets(child)

    def change_language(self, event=None):
        self.root.title(self.tr('Huginn & Muninn — Settings'))
        self.localize_widgets(self.root)
        self.language_status.set(self.tr('Default language') + ': ' + ('Svenska' if self.default_language == 'sv' else 'English'))
        self.theme_picker.configure(values=[self.tr('Dark'), self.tr('Light')])
        self.theme.set(self.tr(self.theme.get()))
        self.show_sites()
        for key, row in self.result_rows.items():
            phase = self.results[key]['phase']
            labels = {'reading': 'Reading', 'analyzing': 'Analyzing', 'complete': 'Analyzed',
                      'failed': 'AI failed', 'interrupted': 'Interrupted', 'skipped': 'Skipped', 'extracted': 'Extracted'}
            values = list(self.result_table.item(row, 'values'))
            values[1] = self.tr(labels.get(phase, phase))
            self.result_table.item(row, values=values)
        self.update_history_status()
        if self.result_table.selection():
            self.show_result()

    def save_default_language(self):
        def action():
            # Save only the preference; unfinished forms need not validate or be saved.
            saved = json.loads(CONFIG.read_text()) if CONFIG.exists() else deepcopy(self.original)
            code = LANGUAGES[self.language.get()]
            saved.setdefault('appearance', {})['language'] = code
            atomic_write(CONFIG, json.dumps(saved, indent=2, ensure_ascii=False).encode())
            self.original.setdefault('appearance', {})['language'] = code
            self.default_language = code
            self.change_language()
            self.log(self.tr('Default language saved.'))
        self.attempt(action)

    def copy_support_info(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(support_summary())
        self.root.update_idletasks()
        self.log(self.tr('Support info copied. ' + version_label()))

    def add_field(self, parent, key, label, row, secret=False):
        self.fields[key] = tk.StringVar()
        ttk.Label(parent, text=self.tr(label), wraplength=180).grid(row=row, column=0, sticky='w', pady=10, padx=(0, 10))
        entry = (ttk.Spinbox(parent, textvariable=self.fields[key], from_=1, to=100, width=8) if key == 'articles_per_site'
                 else ttk.Entry(parent, textvariable=self.fields[key], show='•' if secret else '', width=18))
        entry.grid(row=row, column=1, columnspan=1 if secret else 2, sticky='ew')
        if secret:
            visible = tk.BooleanVar(value=False)
            toggle = ttk.Checkbutton(parent, text=self.tr('Show'), variable=visible, bootstyle='success-round-toggle',
                                     command=lambda: entry.configure(show='' if visible.get() else '•'))
            toggle.grid(row=row, column=2, padx=(8, 0))
            self.secret_controls[key] = (entry, toggle, visible)

    def apply_theme(self):
        self.style.theme_use('flatly' if self.theme.get() in ('Light', 'Ljust') else 'darkly')
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
        self.results_summary.set(self.tr('Waiting for articles…'))

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
            self.update_history_status()
        self.attempt(action)

    def view_history(self):
        selected = self.history_table.selection()
        if not selected:
            return
        def action():
            article = get_article(self.loaded_history_directory, int(selected[0]))
            dialog = tk.Toplevel(self.root)
            dialog.title(self.tr(article.get('title') or 'Saved news'))
            dialog.geometry('850x650')
            text = tk.Text(dialog, wrap='word', padx=20, pady=20)
            scrollbar = ttk.Scrollbar(dialog, command=text.yview)
            text.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side='right', fill='y')
            text.pack(fill='both', expand=True)
            sections = [article.get('title', ''), article.get('url', ''),
                        self.tr('Status: ') + article.get('status', ''), article.get('reason', ''),
                        self.tr('Lead\n') + article.get('lead', ''), self.tr('Analysis\n') + article.get('analysis', ''),
                        self.tr('Article text\n') + article.get('text', '')]
            if article.get('analysis_error'):
                sections.append(self.tr('Analysis failed: {error}', error=article['analysis_error']))
            text.insert('1.0', '\n\n'.join(sections))
            text.configure(state='disabled')
        self.attempt(action)

    def update_history_status(self, event=None):
        if not hasattr(self, 'loaded_history_directory'):
            return
        self.history_status.set(self.tr('{count} matching entries · {selected} selected · {path}',
            count=len(self.history_table.get_children()), selected=len(self.history_table.selection()),
            path=self.loaded_history_directory / 'news-history.sqlite3'))

    def select_all_history(self, event=None):
        self.history_table.selection_set(self.history_table.get_children())
        self.update_history_status()
        return 'break'

    def clear_history_selection(self):
        self.history_table.selection_remove(self.history_table.selection())
        self.update_history_status()

    def delete_history(self):
        selected = self.history_table.selection()
        if not selected:
            messagebox.showinfo(self.tr('No history selected'), self.tr('Select one or more history entries first.'))
            return
        directory = self.loaded_history_directory
        if messagebox.askyesno(self.tr('Delete saved news'), self.tr('Delete {count} selected history entries? This cannot be undone.', count=len(selected))):
            def action():
                delete_entries(directory, selected)
                self.log(self.tr('Deleted {count} saved news entries permanently. Last report and sent emails are kept.', count=len(selected)))
                self.refresh_history()
            self.attempt(action)

    def delete_all_history(self):
        def action():
            # Capture the target before confirmation; search filters do not limit deletion.
            directory = self.history_directory()
            count = len(search_history(directory))
            if not count:
                self.refresh_history()
                return
            if messagebox.askyesno(self.tr('Delete saved news'), self.tr('Delete ALL {count} history entries in {directory}? This includes entries hidden by search. This cannot be undone.', count=count, directory=directory)):
                deleted = delete_all_entries(directory)
                self.log(self.tr('Deleted {count} saved news entries permanently. Last report and sent emails are kept.', count=deleted))
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
        values = (title, self.tr(labels.get(phase, phase)))
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
        self.results_summary.set(self.tr(f'{len(phases)} entries · {phases.count("complete")} analyzed · {phases.count("extracted")} extracted · {phases.count("skipped")} skipped · {phases.count("failed") + phases.count("interrupted")} failed'))
        if phase in ('reading', 'analyzing') and not self.stopping:
            self.run_status.set(self.tr(f'{labels[phase]}: {title[:95]}'))
        elif phase == 'complete':
            self.log(self.tr(f'Analysis ready: {title}'))

    def show_result(self, event=None):
        selected = self.result_table.selection()
        if not selected:
            return
        item = self.results[self.row_keys[selected[0]]]
        article, phase = item['article'], item['phase']
        analysis = article.get('analysis')
        if not analysis:
            analysis = article.get('analysis_error') or {
                'reading': self.tr('Fetching the article…'), 'analyzing': self.tr('Waiting for the model to return the analysis…'),
                'skipped': self.tr('No AI analysis: {reason}', reason=article.get('reason') or self.tr('Not enough readable article text.')),
                'extracted': self.tr('Extraction only; no analysis was requested.')}.get(phase, self.tr('No analysis returned.'))
        text = self.result_text
        text.configure(state='normal')
        text.delete('1.0', 'end')
        text.insert('end', (article.get('title') or self.tr('Reading article…')) + '\n', 'title')
        text.insert('end', article.get('url', '') + '\n', 'metadata')
        status = self.tr(article.get('status', 'reading').replace('_', ' ').capitalize())
        text.insert('end', f"{status}  ·  {article.get('source', '')}\n", 'metadata')
        if article.get('reason'):
            text.insert('end', article['reason'] + '\n', 'metadata')
        for heading, value, markdown in [('Lead paragraph', article.get('lead') or self.tr('Not available yet.'), False),
                                          ('Analysis', analysis, True),
                                          ('Article text', article.get('text') or self.tr('No readable article text was available.'), False)]:
            text.insert('end', self.tr(heading) + '\n', 'section')
            if markdown:
                for content, tags in markdown_spans(value):
                    text.insert('end', content, tags)
            else:
                text.insert('end', value + '\n', 'body')
        text.configure(state='disabled')

    def preview_email(self):
        if not self.results:
            messagebox.showinfo(self.tr('No entries yet'), self.tr('Run an analysis, test a site, or load the last report first.'))
            return
        def action():
            articles = [item['article'] for item in self.results.values()]
            _, html = render_report(articles)
            path = DATA_DIRECTORY / 'email-preview.html'
            atomic_write(path, html.encode('utf-8'))
            webbrowser.open(path.as_uri())
            self.log(self.tr('Email layout opened in your browser. Preview does not send an email.'))
        self.attempt(action)

    def load_last_report(self):
        if getattr(self, 'preview_active', False) or (self.process and self.process.poll() is None):
            self.tabs.select(self.results_page)
            self.log(self.tr('A run is in progress. Its live entries are shown in Results.'))
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
                self.results_summary.set(self.tr('The last report contains no articles.'))
            self.tabs.select(self.results_page)
            self.log(self.tr(f'Loaded {len(articles)} entries from {path}.'))
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
            self.run_elapsed.set(self.tr(f'{elapsed // 60:02d}:{elapsed % 60:02d} elapsed'))
        self.root.after(1000, self.update_run_clock)

    def restore_prompt(self):
        self.prompt_editor.delete('1.0', 'end')
        self.prompt_editor.insert('1.0', DEFAULT_ANALYSIS_PROMPT)
        self.log(self.tr('Default prompt restored in the editor. Save settings to keep it.'))

    def change_theme(self, event=None):
        self.apply_theme()

    def choose_deployment(self):
        directory = filedialog.askdirectory(title=self.tr('Choose deployment folder'))
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
            messagebox.showerror(self.tr('Could not complete action'), self.tr(str(error)))

    def change_smtp_security(self, event=None):
        if self.fields['smtp_port'].get().strip() in ('465', '587', '25'):
            self.fields['smtp_port'].set(str({'ssl': 465, 'starttls': 587, 'none': 25}[self.smtp_security.get()]))

    def smtp_form_data(self):
        smtp = deepcopy(self.original.get('smtp', {}))
        for key in ('host', 'username', 'sender'):
            smtp[key] = self.fields['smtp_' + key].get().strip()
        try:
            smtp['port'] = int(self.fields['smtp_port'].get())
        except ValueError:
            raise ValueError('SMTP port must be a whole number from 1 to 65535.')
        smtp.update(security=self.smtp_security.get(), authenticate=self.smtp_authenticate.get())
        return {'smtp': smtp, 'email': self.fields['email'].get().strip(), 'app_password': self.fields['app_password'].get()}

    def test_email_connection(self):
        def action():
            data = self.smtp_form_data()
            smtp_options(data)
            self.smtp_test_button.configure(state='disabled')
            self.log(self.tr('Testing SMTP connection; no email will be sent…'))
            def check():
                try:
                    test_smtp_connection(data)
                    result = 'SMTP connection succeeded. No email was sent.'
                except Exception as error:
                    # Provider responses may contain account identifiers; omit raw credentials.
                    result = 'SMTP connection failed. Check server, port, encryption and credentials. (' + type(error).__name__ + ')'
                self.events.put(('smtp-test', result))
            threading.Thread(target=check, daemon=True).start()
        self.attempt(action)

    def data(self):
        data = deepcopy(self.original)
        for key in ('use_openai', 'openai_api_key', 'openai_model'):
            data.pop(key, None)
        for key, variable in self.fields.items():
            if key != 'deployment_directory' and not key.startswith('smtp_'):
                data[key] = variable.get() if key == 'app_password' else variable.get().strip()
        if hasattr(self, 'smtp_security'):
            data.update(self.smtp_form_data())
        data['app_password'] = smtp_options(data)['password']
        try:
            data['articles_per_site'] = int(data['articles_per_site'])
        except ValueError:
            raise ValueError('Articles per site must be a whole number.')
        if 'deployment_directory' in self.fields:
            data.setdefault('deployment', {})['directory'] = self.fields['deployment_directory'].get().strip()
        if hasattr(self, 'deployment_backups'):
            data.setdefault('deployment', {})['backups'] = self.deployment_backups.get()
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
            data.setdefault('appearance', {})['theme'] = 'flatly' if self.theme.get() in ('Light', 'Ljust') else 'darkly'
        return validate(data)

    def display(self, data):
        self.original = deepcopy(data)
        if hasattr(self, 'language'):
            self.default_language = data.get('appearance', {}).get('language', 'en')
            self.language.set('Svenska' if self.default_language == 'sv' else 'English')
        self.prompt_editor.delete('1.0', 'end')
        self.prompt_editor.insert('1.0', get_analysis_prompt(data))
        self.prompt_editor.edit_reset()
        if hasattr(self, 'theme'):
            self.theme.set('Light' if data.get('appearance', {}).get('theme') == 'flatly' else 'Dark')
            self.apply_theme()
        defaults = dict(articles_per_site=DEFAULT_ARTICLE_LIMIT, gemini_search_model=DEFAULT_MODEL)
        if hasattr(self, 'search_related_coverage'):
            self.search_related_coverage.set(data.get('search_related_coverage', False))
        smtp = data.get('smtp', {})
        if hasattr(self, 'smtp_security'):
            self.smtp_security.set(smtp.get('security', 'ssl'))
            self.smtp_authenticate.set(smtp.get('authenticate', True))
        for key, variable in self.fields.items():
            if key.startswith('smtp_'):
                variable.set(smtp.get(key[5:], {'host': 'smtp.gmail.com', 'port': {'ssl': 465, 'starttls': 587, 'none': 25}.get(smtp.get('security', 'ssl'), 465)}.get(key[5:], '')))
                continue
            variable.set(data.get('deployment', {}).get('directory', str(DEFAULT_DIRECTORY)) if key == 'deployment_directory' else data.get(key, defaults.get(key, '')))
        self.model.set(data.get('ollama_model', 'llama3.2:latest'))
        if hasattr(self, 'deployment_backups'):
            self.deployment_backups.set(data.get('deployment', {}).get('backups', True))
        self.sites = [deepcopy(site) if isinstance(site, dict) else {'url': site, 'selector': '', 'enabled': True}
                      for site in data.get('news_sites', DEFAULT_SITES)]
        self.show_sites()
        self.change_language()

    def show_sites(self):
        self.site_table.delete(*self.site_table.get_children())
        self.source_count.set(self.tr('{count} sources · {enabled} enabled', count=len(self.sites), enabled=sum(site.get('enabled', True) for site in self.sites)))
        for index, site in enumerate(self.sites):
            self.site_table.insert('', 'end', iid=str(index), values=(site['url'], site.get('selector', ''), site.get('articles_per_site', self.tr('Default')), self.tr('Enabled' if site.get('enabled', True) else 'Paused')))

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
        path = filedialog.askopenfilename(title=self.tr('Import settings'), filetypes=[('Config files', '*.json')])
        if path:
            def action():
                with open(path) as stream:
                    data = validate(json.load(stream))
                self.expression.set(data.get('schedule', {}).get('expression', '0 10,19 * * *'))
                self.display(data)
                self.log(self.tr('Settings imported. Save config to keep them.'))
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
            self.model_status.set(self.tr('Loading models…'))
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
            self.model_status.set(self.tr('Server changed. Refresh models again.'))
            return
        if error:
            self.model_status.set(self.tr('Could not load models. See output.'))
            self.log(self.tr('Ollama: ' + error + '. Check that Ollama is running and the URL is correct.'))
            return
        self.model_picker.configure(values=names)
        selected = self.model.get()
        self.model.set(selected)
        self.model_status.set(self.tr(f'{len(names)} models available.' if names else 'No models installed. Use ollama pull <model>.'))
        if names and selected not in names:
            self.model_status.set(self.tr('Configured model unavailable. Select an installed model.'))

    def save(self):
        def action():
            save_config(self.data())
            self.log(self.tr('Saved config.json.'))
            return True
        return self.attempt(action)

    def change_site(self, mode):
        selected = self.site_table.selection()
        if mode != 'add' and not selected:
            messagebox.showinfo(self.tr('Select a site'), self.tr('Select a site in the table first.'))
            return
        index = int(selected[0]) if selected else None
        if mode == 'delete':
            self.sites.pop(index)
            self.show_sites()
            return
        old = deepcopy(self.sites[index]) if mode == 'edit' else {'url': '', 'selector': '', 'enabled': True}
        dialog = tk.Toplevel(self.root)
        dialog.title(self.tr('Edit site' if mode == 'edit' else 'Add site'))
        dialog.transient(self.root)
        dialog.grab_set()
        url = tk.StringVar(value=old['url'])
        selector = tk.StringVar(value=old.get('selector', ''))
        feed = tk.StringVar(value=old.get('feed_url', ''))
        enabled = tk.BooleanVar(value=old.get('enabled', True))
        site_limit = tk.StringVar(value=old.get('articles_per_site', ''))
        for row, (label, variable) in enumerate([('Site URL', url), ('CSS selector (optional)', selector), ('RSS/Atom URL (optional)', feed)]):
            ttk.Label(dialog, text=self.tr(label)).grid(row=row, column=0, padx=10, pady=8, sticky='w')
            ttk.Entry(dialog, textvariable=variable, width=55).grid(row=row, column=1, padx=10)
        ttk.Label(dialog, text=self.tr('Articles (blank = default)')).grid(row=3, column=0, padx=10, pady=8, sticky='w')
        ttk.Spinbox(dialog, textvariable=site_limit, from_=1, to=100, width=10).grid(row=3, column=1, padx=10, sticky='w')
        ttk.Checkbutton(dialog, text=self.tr('Enabled'), variable=enabled).grid(row=4, column=1, sticky='w')
        ttk.Label(dialog, text=self.tr('Just enter a site URL. Feed and selector override automatic discovery.')).grid(row=5, column=0, columnspan=2, padx=10, pady=8)
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
                validate(dict(email='placeholder', app_password='placeholder',
                              ollama_base_url='http://localhost:11434', news_sites=[site]))
                if mode == 'edit':
                    self.sites[index] = site
                else:
                    self.sites.append(site)
                self.show_sites()
                dialog.destroy()
            self.attempt(action)
        ttk.Button(dialog, text=self.tr('Apply'), command=apply).grid(row=6, column=1, sticky='e', padx=10, pady=10)
        ttk.Button(dialog, text=self.tr('Cancel'), command=dialog.destroy).grid(row=6, column=0, padx=10, pady=10)

    def add_site(self): self.change_site('add')
    def edit_site(self): self.change_site('edit')
    def delete_site(self): self.change_site('delete')

    def preview_site(self):
        if self.preview_active or (self.process and self.process.poll() is None):
            self.tabs.select(self.results_page)
            self.log(self.tr('A run or site test is already in progress. Use Stop run before starting another.'))
            return
        selected = self.site_table.selection()
        if not selected:
            messagebox.showinfo(self.tr('Select a site'), self.tr('Select a site to test first.'))
            return
        try:
            configured = int(self.fields['articles_per_site'].get())
            source = deepcopy(self.sites[int(selected[0])])
            limit = article_limit({'articles_per_site': configured}, source)
        except (ValueError, TypeError) as error:
            messagebox.showerror(self.tr('Invalid article limit'), self.tr(str(error)))
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
        self.run_status.set(self.tr(f'Testing site · up to {limit} articles…'))
        self.set_running(True)
        self.log(self.tr(f"Testing {source['url']} · limit {limit} · extraction only, no AI or email."))
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
            self.log(self.tr(f'Deployed version to {directory}.{detail} Schedule unchanged.'))
        self.attempt(action)

    def install(self):
        def action():
            data = self.data()
            data.setdefault('schedule', {})['expression'] = self.expression.get()
            save_config(data)
            self.display(data)
            directory, backup = update_cron(self.expression.get(), data)
            detail = f' Backup: {backup}.' if backup else ' No backup created.'
            self.log(self.tr(f'Deployed and scheduled in {directory}.{detail} Output: {directory / "news-analysis.log"}'))
        self.attempt(action)

    def manage_backups(self):
        def action():
            config = {'deployment': {
                'directory': self.fields['deployment_directory'].get().strip(),
                'backups': self.deployment_backups.get(),
            }}
            dialog = tk.Toplevel(self.root)
            dialog.title(self.tr('Deployment backups'))
            dialog.geometry('760x430')
            dialog.transient(self.root)
            dialog.grab_set()
            ttk.Label(dialog, text=self.tr(str(deployment_directory(config))), bootstyle='secondary', wraplength=720).pack(anchor='w', padx=18, pady=(18, 10))
            table = ttk.Treeview(dialog, columns=('version', 'files', 'size'), show='headings', selectmode='extended')
            for key, label, width in [('version', 'UTC VERSION', 360), ('files', 'FILES', 90), ('size', 'SIZE', 130)]:
                table.heading(key, text=self.tr(label))
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
                    messagebox.showinfo(self.tr('No backups selected'), self.tr('Select one or more backup versions first.'), parent=dialog)
                    return
                label = f'{len(names)} selected backup version' if selected_only else 'all backup versions'
                if not messagebox.askyesno(self.tr('Delete backups'), self.tr(f'Delete {label}{"s" if selected_only and len(names) != 1 else ""}? This cannot be undone.'), parent=dialog):
                    return
                deleted = delete_backups(config, names)
                self.log(self.tr(f'Deleted {len(deleted)} deployment backup version(s).'))
                refresh()
            actions = ttk.Frame(dialog)
            actions.pack(fill='x', padx=18, pady=(2, 18))
            ttk.Button(actions, text=self.tr('Delete selected'), command=lambda: remove(True), bootstyle='danger-outline').pack(side='left')
            ttk.Button(actions, text=self.tr('Delete all'), command=lambda: remove(False), bootstyle='danger').pack(side='left', padx=8)
            ttk.Button(actions, text=self.tr('Close'), command=dialog.destroy, bootstyle='secondary-outline').pack(side='right')
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
        self.attempt(lambda: (update_cron(), self.log(self.tr('Managed cron schedule removed.'))))

    def show_cron(self):
        self.attempt(lambda: self.log(self.tr(read_crontab() or 'No crontab installed.')))

    def run(self, resend_report=False):
        if getattr(self, 'preview_active', False) or (self.process and self.process.poll() is None):
            self.tabs.select(self.results_page)
            self.log(self.tr('Run in progress. Select an entry in Results to inspect it, or use Stop run.'))
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
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=self.tr(True), encoding='utf-8', errors='replace',
                                            start_new_session=(os.name != 'nt'))
            self.run_id += 1
            run_id, process = self.run_id, self.process
            self.stopping = False
            if not resend_report:
                self.clear_results()
            self.tabs.select(self.results_page)
            self.run_started = time.monotonic()
            self.run_status.set(self.tr('Sending saved report…' if resend_report else 'Starting analysis…'))
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
            self.log(self.tr('Sending the saved report only. No scraping or AI requests.' if resend_report else 'Analysis started. Live entries and their analyses appear in Results.'))
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
            self.run_status.set(self.tr('Stopping site test after the current request…'))
            self.stop_button.configure(state='disabled')
            return
        if self.process and self.process.poll() is None:
            self.stopping = True
            self.run_status.set(self.tr('Stopping analysis…'))
            self.stop_button.configure(state='disabled')
            process = self.process
            self.signal_process(process)
            self.root.after(5000, lambda: self.signal_process(process, force=True))
            self.log(self.tr('Stop requested. Entries received so far remain visible.'))

    def handle_run_message(self, event):
        kind, run_id, payload = event
        if run_id != self.run_id:
            return
        if kind == 'run-log':
            self.log(self.tr(payload))
        elif kind == 'run-event':
            if payload['type'] == 'article':
                self.upsert_result(payload)
            elif payload['type'] == 'progress':
                if not self.stopping:
                    self.run_status.set(self.tr(payload.get('message', 'Running…')))
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
                self.results_summary.set(self.tr('No articles were received. See activity messages for details.'))
            display_status = self.tr(status) + f' (exit {payload})' if payload and not self.stopping else self.tr(status)
            self.run_status.set(self.tr(f'{display_status} · {self.results_summary.get()}'))
            self.log(self.tr(f'{display_status}.'))

    def poll(self):
        # Bound each batch so a large report cannot starve redraws and Stop run.
        for _ in range(100):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if isinstance(event, tuple) and event[0] == 'smtp-test':
                self.smtp_test_button.configure(state='normal')
                self.log(self.tr(event[1]))
                messagebox.showinfo(self.tr('SMTP connection test'), self.tr(event[1]))
            elif isinstance(event, tuple) and event[0] == 'models':
                self.receive_models(*event[1:])
            elif isinstance(event, tuple) and event[0].startswith('run-'):
                self.handle_run_message(event)
            else:
                self.log(self.tr(event))
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
        Path(sys.argv[sys.argv.index('--smoke-test') + 1]).write_text(json.dumps({'version': build_info()['version'], 'build_id': build_info()['build_id'], 'title': root.title(), 'language': LANGUAGES[editor.language.get()], 'fields': list(editor.fields), 'sites': len(editor.sites), 'config_path': str(CONFIG), 'theme': editor.style.theme_use(), 'tabs': [editor.tabs.tab(tab, 'text') for tab in editor.tabs.tabs()]}))
        root.destroy()
    else:
        root.mainloop()
