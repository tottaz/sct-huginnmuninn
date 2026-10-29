"""Release identity shared by the builder and desktop UI."""
import json
import platform
import sys
from pathlib import Path

APP_NAME = 'Huginn Muninn'
APP_ID = 'tech.socialclimate.huginnmuninn'
_version_path = Path(__file__).resolve().parent / 'VERSION'
VERSION = _version_path.read_text().strip() if _version_path.is_file() else '1.0.0'


def build_info():
    path = Path(__file__).resolve().parent / 'build-info.json'
    if path.is_file():
        return json.loads(path.read_text())
    return {'version': VERSION, 'build_id': 'source'}


def version_label():
    info = build_info()
    return f"Version {info['version']} · build {info['build_id']}"


def support_summary():
    info = build_info()
    return (f"{APP_NAME}\nVersion: {info['version']}\nBuild: {info['build_id']}\n"
            f"System: {platform.system()} {platform.release()} ({platform.machine()})\n"
            f"Python: {platform.python_version()}\n"
            f"Mode: {'Packaged app' if getattr(sys, 'frozen', False) else 'Source'}")
