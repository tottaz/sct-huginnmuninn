"""Small, non-executable Markdown formatter for Tk article results."""
import re

INLINE = re.compile(r'(`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|\[[^\]\n]+\]\(https?://[^)\s]+\)|(?<!\*)\*[^*\n]+\*(?!\*))')


def inline_spans(text, tags=()):
    cursor = 0
    for match in INLINE.finditer(text):
        if match.start() > cursor:
            yield text[cursor:match.start()], tags
        value = match.group()
        if value.startswith('`'):
            yield value[1:-1], (*tags, 'code')
        elif value.startswith(('**', '__')):
            yield value[2:-2], (*tags, 'strong')
        elif value.startswith('*'):
            yield value[1:-1], (*tags, 'emphasis')
        else:
            label, url = re.match(r'\[([^]]+)\]\((.+)\)', value).groups()
            yield f'{label} ({url})', (*tags, 'link')
        cursor = match.end()
    if cursor < len(text):
        yield text[cursor:], tags


def markdown_spans(text):
    """Return text/tag pairs; HTML and model-supplied code are never executed."""
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith('```'):
            fenced = not fenced
            continue
        if fenced:
            yield line + '\n', ('codeblock',)
            continue
        heading = re.match(r'^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$', line)
        bullet = re.match(r'^\s*[-*+]\s+(.+)', line)
        number = re.match(r'^\s*(\d+[.)])\s+(.+)', line)
        if heading:
            yield from inline_spans(heading[1], ('heading',))
            yield '\n', ('heading',)
        elif bullet:
            yield '• ', ('list',)
            yield from inline_spans(bullet[1], ('list',))
            yield '\n', ('list',)
        elif number:
            yield number[1] + ' ', ('list',)
            yield from inline_spans(number[2], ('list',))
            yield '\n', ('list',)
        elif re.fullmatch(r'\s*(?:-{3,}|\*{3,}|_{3,})\s*', line):
            yield '────────────────────────\n', ('metadata',)
        else:
            yield from inline_spans(line, ('body',))
            yield '\n', ('body',)
