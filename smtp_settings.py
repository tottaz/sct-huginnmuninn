"""Provider-neutral SMTP settings with backwards-compatible Gmail defaults."""
from contextlib import contextmanager
import smtplib
import ssl


def settings(config, require_password=True):
    smtp = config.get('smtp', {})
    if not isinstance(smtp, dict):
        raise ValueError('SMTP settings must be an object.')
    host = smtp.get('host', 'smtp.gmail.com')
    if not isinstance(host, str) or not host.strip() or any(c.isspace() for c in host) or '://' in host:
        raise ValueError('Enter an SMTP hostname without a URL scheme or spaces.')
    host = host.strip()
    security = smtp.get('security', 'ssl')
    if security not in ('ssl', 'starttls', 'none'):
        raise ValueError('SMTP encryption must be ssl, starttls or none.')
    port = smtp.get('port', {'ssl': 465, 'starttls': 587, 'none': 25}[security])
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('SMTP port must be a whole number from 1 to 65535.')
    auth = smtp.get('authenticate', True)
    if not isinstance(auth, bool):
        raise ValueError('SMTP authentication must be true or false.')
    recipient = config.get('email', '')
    sender = smtp.get('sender', '') or recipient
    username = smtp.get('username', '') or recipient
    for label, value in [('recipient', recipient), ('sender', sender), ('username', username)]:
        if not isinstance(value, str) or '\n' in value or '\r' in value:
            raise ValueError(f'SMTP {label} must be a single line of text.')
    if not recipient.strip() or not sender.strip() or (auth and not username.strip()):
        raise ValueError('Enter the recipient, sender and SMTP username.')
    password = config.get('app_password', '')
    if not isinstance(password, str):
        raise ValueError('SMTP password must be text.')
    # Google displays app passwords in groups. Other servers may use real spaces.
    if host.lower() == 'smtp.gmail.com':
        password = ''.join(password.split())
    if auth and require_password and not password:
        raise ValueError('Enter an SMTP password or app password before sending email.')
    return dict(host=host, port=port, security=security, authenticate=auth,
                recipient=recipient.strip(), sender=sender.strip(), username=username.strip(), password=password)


@contextmanager
def connection(options):
    """Require the selected encryption; never fall back after a TLS failure."""
    context = ssl.create_default_context()
    factory = smtplib.SMTP_SSL if options['security'] == 'ssl' else smtplib.SMTP
    kwargs = {'timeout': 30}
    if options['security'] == 'ssl':
        kwargs['context'] = context
    with factory(options['host'], options['port'], **kwargs) as server:
        if options['security'] == 'starttls':
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
        if options['authenticate']:
            server.login(options['username'], options['password'])
        yield server


def test_connection(config):
    """Connect, negotiate encryption and optionally sign in, without sending mail."""
    options = settings(config)
    with connection(options) as server:
        code, _ = server.noop()
        if code != 250:
            raise RuntimeError('The SMTP server did not confirm the connection.')
    return f"SMTP connection succeeded: {options['host']}:{options['port']}"
