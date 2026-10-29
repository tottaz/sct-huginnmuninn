"""Line protocol for optional, immediately flushed analysis progress events."""
import json

PREFIX = 'HUGINN_EVENT '


def emit_event(event):
    print(PREFIX + json.dumps(event, ensure_ascii=False), flush=True)


def parse_event(line):
    if not line.startswith(PREFIX):
        return None
    try:
        event = json.loads(line[len(PREFIX):])
    except ValueError:
        return None
    if not isinstance(event, dict) or event.get('type') not in ('article', 'progress'):
        return None
    if event['type'] == 'article' and (not isinstance(event.get('id'), str) or not isinstance(event.get('article'), dict)):
        return None
    return event
