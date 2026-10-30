"""Select an existing project environment before importing desktop dependencies."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

UI_MODULES = ('tkinter', 'ttkbootstrap', 'requests', 'bs4')


def ensure_ui_runtime(script):
    if getattr(sys, 'frozen', False):
        return
    missing = [module for module in UI_MODULES if importlib.util.find_spec(module) is None]
    if not missing:
        return
    root = Path(script).resolve().parent
    for name in ('.venv', '.venv-build'):
        environment = root / name
        candidate = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if not candidate.is_file() or Path(sys.prefix).absolute() == environment.absolute():
            continue
        try:
            check = subprocess.run([str(candidate), '-c', '; '.join('import ' + module for module in UI_MODULES)],
                                   capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if check.returncode == 0:
            os.execv(str(candidate), [str(candidate), str(Path(script).resolve()), *sys.argv[1:]])
    modules = ', '.join(missing)
    raise SystemExit(
        f'UI dependencies missing: {modules}.\n'
        'Open the packaged Huginn Muninn app, or install the source dependencies:\n'
        f'  "{sys.executable}" -m pip install -r "{root / "requirements.txt"}"\n'
        'Then launch config_ui.py again. A compatible .venv or .venv-build is selected automatically.'
    )
