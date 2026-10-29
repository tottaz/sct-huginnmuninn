"""Build matching plain-text and Gmail-friendly HTML news reports."""
from html import escape
import re
from urllib.parse import urlsplit

from result_formatting import inline_spans, markdown_spans


LINK_STYLE = 'color:#16736b;text-decoration:underline;'


def safe_link(url, label):
    url = str(url or '')
    parsed = urlsplit(url)
    if parsed.scheme in ('http', 'https') and parsed.hostname and not parsed.username and not any(ord(char) < 32 for char in url):
        return f'<a href="{escape(url, quote=True)}" style="{LINK_STYLE}">{escape(str(label))}</a>'
    return escape(str(label))


def inline_html(text):
    parts = []
    for value, tags in inline_spans(text):
        content = escape(value)
        if 'strong' in tags:
            content = f'<strong>{content}</strong>'
        elif 'emphasis' in tags:
            content = f'<em>{content}</em>'
        elif 'code' in tags:
            content = f'<code style="font-family:monospace;background-color:#edf2f0;padding:2px 4px;">{content}</code>'
        elif 'link' in tags:
            match = re.fullmatch(r'(.*) \((https?://.*)\)', value)
            if match:
                content = safe_link(match[2], match[1])
        parts.append(content)
    return ''.join(parts)


def markdown_html(text):
    output, paragraph, code = [], [], []
    list_kind = None
    fenced = False
    def flush_paragraph():
        if paragraph:
            output.append('<p style="margin:0 0 12px;line-height:1.65;">' + '<br>'.join(inline_html(line) for line in paragraph) + '</p>')
            paragraph.clear()
    def close_list():
        nonlocal list_kind
        if list_kind:
            output.append(f'</{list_kind}>')
            list_kind = None
    def flush_code():
        if code:
            output.append('<pre style="white-space:pre-wrap;font-family:monospace;background-color:#edf2f0;padding:12px;border-radius:6px;"><code>' + escape('\n'.join(code)) + '</code></pre>')
            code.clear()
    for line in text.splitlines():
        if line.lstrip().startswith('```'):
            flush_paragraph()
            close_list()
            if fenced:
                flush_code()
            fenced = not fenced
            continue
        if fenced:
            code.append(line)
            continue
        heading = re.match(r'^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$', line)
        bullet = re.match(r'^\s*[-*+]\s+(.+)', line)
        number = re.match(r'^\s*(\d+)[.)]\s+(.+)', line)
        if heading:
            flush_paragraph()
            close_list()
            output.append('<h3 style="font-size:17px;line-height:1.4;color:#164b46;margin:20px 0 8px;">' + inline_html(heading[2]) + '</h3>')
        elif bullet or number:
            flush_paragraph()
            kind = 'ul' if bullet else 'ol'
            if list_kind != kind:
                close_list()
                start = f' start="{int(number[1])}"' if number else ''
                output.append(f'<{kind}{start} style="margin:0 0 14px;padding-left:24px;">')
                list_kind = kind
            content = bullet[1] if bullet else number[2]
            output.append('<li style="margin:0 0 7px;line-height:1.6;">' + inline_html(content) + '</li>')
        elif re.fullmatch(r'\s*(?:-{3,}|\*{3,}|_{3,})\s*', line):
            flush_paragraph()
            close_list()
            output.append('<hr style="border:0;border-top:1px solid #dce5e1;margin:18px 0;">')
        elif not line.strip():
            flush_paragraph()
            close_list()
        else:
            close_list()
            paragraph.append(line)
    flush_paragraph()
    close_list()
    flush_code()
    return ''.join(output)


def render_report(articles, source_errors=()):
    plain_entries, cards = [], []
    for item in articles:
        title = item.get('title') or '(Title unavailable)'
        url = item.get('url', '')
        status = item.get('status', 'unavailable')
        lead = item.get('lead', '')
        analysis = item.get('analysis', '')
        reason = item.get('reason', '')
        error = item.get('analysis_error', '')
        entry = f'Title: {title}\nArticle: {url}\nStatus: {status}\n{reason}'
        if lead:
            entry += '\nLead: ' + lead
        if analysis:
            entry += '\nAnalysis:\n' + ''.join(content for content, _ in markdown_spans(analysis)).rstrip()
        if error:
            entry += '\nAnalysis failed: ' + error
        plain_entries.append(entry)
        label = 'Analyzed' if analysis else 'Analysis failed' if error else 'Extracted' if status == 'article' else status.capitalize()
        if item.get('analysis_origin') == 'related_coverage':
            label = 'Summary from related coverage'
        badge_bg, badge_fg = ('#e5f2eb', '#215a3f') if analysis else ('#fff2d8', '#775219')
        card = ('<tr><td style="padding:26px 28px;border-bottom:1px solid #dce5e1;">'
                f'<span style="display:inline-block;font-size:12px;font-weight:bold;background-color:{badge_bg};color:{badge_fg};padding:4px 10px;border-radius:12px;">{escape(label)}</span>'
                f'<h2 style="font-size:22px;line-height:1.35;margin:12px 0 8px;color:#173c38;">{safe_link(url, title)}</h2>'
                f'<p style="font-size:13px;color:#687772;margin:0 0 14px;">{escape(str(item.get("source", "")))}</p>')
        if reason:
            card += f'<p style="font-size:13px;color:#687772;margin:0 0 14px;">{escape(reason)}</p>'
        if lead:
            card += '<div style="border-left:3px solid #caad6a;padding:4px 0 4px 14px;margin:16px 0 20px;line-height:1.65;">' + escape(lead).replace('\n', '<br>') + '</div>'
        if analysis:
            card += '<div style="color:#243c35;">' + markdown_html(analysis) + '</div>'
        elif error:
            card += f'<p style="color:#9c3631;line-height:1.6;">Analysis failed: {escape(error)}</p>'
        else:
            card += '<p style="color:#687772;line-height:1.6;">No AI analysis was generated for this entry.</p>'
        card += '<p style="margin:16px 0 0;font-size:13px;">' + safe_link(url, 'Read the original article →') + '</p></td></tr>'
        cards.append(card)
    issues = []
    for item in source_errors:
        url, reason = str(item.get('url', '')), str(item.get('reason', ''))
        plain_entries.append(f'Source: {url}\nSkipped: {reason}')
        issues.append('<li style="margin-bottom:8px;">' + safe_link(url, url) + ': ' + escape(reason) + '</li>')
    if issues:
        cards.append('<tr><td style="padding:24px 28px;"><h2 style="font-size:18px;color:#775219;">Sources that could not be read</h2><ul style="padding-left:20px;line-height:1.6;">' + ''.join(issues) + '</ul></td></tr>')
    if not cards:
        cards.append('<tr><td style="padding:28px;">No articles found.</td></tr>')
    analyzed = sum(bool(item.get('analysis')) for item in articles)
    plain = 'Latest news extraction and analysis\n\n' + ('\n\n'.join(plain_entries) or 'No articles found.')
    html = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Huginn &amp; Muninn — News analysis</title></head>'
            '<body style="margin:0;padding:0;background-color:#eef3f0;color:#243c35;font-family:Arial,Helvetica,sans-serif;">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#eef3f0;"><tr><td align="center" style="padding:24px 12px;">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:720px;background-color:#ffffff;border:1px solid #dce5e1;border-radius:12px;">'
            '<tr><td style="padding:28px;background-color:#173e3b;color:#ffffff;border-radius:12px 12px 0 0;">'
            '<p style="color:#d9bd7b;font-size:12px;letter-spacing:2px;font-weight:bold;margin:0 0 10px;">HUGINN &amp; MUNINN</p>'
            '<h1 style="font-size:28px;line-height:1.25;margin:0 0 12px;color:#ffffff;">Your daily perspective</h1>'
            f'<p style="margin:0;color:#d7e4de;font-size:14px;">{len(articles)} entries &nbsp;·&nbsp; {analyzed} analyzed</p></td></tr>'
            + ''.join(cards)
            + '<tr><td style="padding:20px 28px;color:#687772;font-size:12px;line-height:1.6;">Prepared by Huginn &amp; Muninn. AI analysis is based on extracted public text and may be incomplete. Follow source links to read the original reporting.</td></tr>'
            '</table></td></tr></table></body></html>')
    return plain, html
