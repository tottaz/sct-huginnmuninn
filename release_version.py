"""Reserve a unique, persistent patch version for each full build attempt."""
import os
from pathlib import Path
import re
import tempfile
from app_version import VERSION


def version_parts(value):
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value):
        raise ValueError('Version must have three numbers without leading zeros, for example 1.0.1.')
    return tuple(map(int, value.split('.')))


def reserve_version(root, requested=None):
    root = Path(root)
    lock = root / '.build-version.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RuntimeError('Another build is reserving a version. Wait for it to finish; if a build crashed, remove .build-version.lock only after checking no build is running.') from error
    temporary = None
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        path = root / 'VERSION'
        current = version_parts(path.read_text().strip() if path.exists() else VERSION)
        selected = version_parts(requested) if requested is not None else (current[0], current[1], current[2] + 1)
        if selected <= current:
            raise ValueError('An explicit version must be newer than the last reserved build version.')
        version = '.'.join(map(str, selected))
        fd, temporary = tempfile.mkstemp(prefix='.version-', dir=root)
        with os.fdopen(fd, 'w') as stream:
            stream.write(version + '\n')
        os.replace(temporary, path)
        return version
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
