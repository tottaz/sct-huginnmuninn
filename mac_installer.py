"""Reversible app installation without changing settings or cron deployments."""
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import uuid

from app_version import APP_ID, APP_NAME


def bundle_info(app):
    app = Path(app)
    info = plistlib.loads((app / 'Contents' / 'Info.plist').read_bytes())
    executable = info.get('CFBundleExecutable')
    if not isinstance(executable, str) or Path(executable).name != executable or not (app / 'Contents' / 'MacOS' / executable).is_file():
        raise ValueError('The application bundle is incomplete; rebuild the app before installing.')
    return info


def running_from(app):
    executable = Path(app) / 'Contents' / 'MacOS' / bundle_info(app)['CFBundleExecutable']
    result = subprocess.run(['ps', '-axo', 'command='], capture_output=True, text=True, check=True, timeout=10)
    return any(line.strip() == str(executable) or line.strip().startswith(str(executable) + ' ') for line in result.stdout.splitlines())


def install_app(source, destination, backup_root, check_running=running_from):
    source, destination, backup_root = map(Path, (source, destination, backup_root))
    if source.resolve() == destination.resolve():
        raise ValueError('This copy is already installed in the selected folder.')
    if source.resolve() in destination.resolve().parents or destination.resolve() in source.resolve().parents:
        raise ValueError('Choose an Applications folder outside the source app bundle.')
    info = bundle_info(source)
    if info.get('CFBundleIdentifier') != APP_ID:
        raise ValueError('This installer requires a new Huginn Muninn build with a valid app identifier.')
    if destination.is_symlink():
        raise ValueError('The destination app is a symbolic link. Choose a regular Applications folder.')
    if destination.exists():
        old_info = bundle_info(destination)
        if old_info.get('CFBundleIdentifier') not in (APP_ID, APP_NAME):
            raise ValueError('The destination belongs to another application; choose another folder.')
        if check_running(destination):
            raise ValueError('Quit the installed Huginn Muninn app, then run Install or Update again. An active analysis should finish or be stopped before quitting.')
    token = uuid.uuid4().hex[:10]
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / f'.huginn-install-{token}.app'
    previous = destination.parent / f'.huginn-previous-{token}.app'
    backup = None
    try:
        shutil.copytree(source, staging, symlinks=True)
        bundle_info(staging)
        if destination.exists():
            backup = backup_root / f'{APP_NAME}-{token}.app'
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(destination, backup, symlinks=True)
            destination.rename(previous)
        try:
            staging.rename(destination)
        except Exception:
            if previous.exists():
                previous.rename(destination)
            raise
        if previous.exists():
            shutil.rmtree(previous, ignore_errors=True)
        return backup
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def install_dialog():
    import tkinter as tk
    from tkinter import filedialog, messagebox
    root = tk.Tk()
    root.withdraw()
    try:
        if sys.platform != 'darwin' or not getattr(sys, 'frozen', False):
            raise ValueError('Open Install or Update.command from the built Mac disk image.')
        source = Path(sys.executable).resolve().parents[2]
        folder = filedialog.askdirectory(title='Install or update Huginn Muninn', initialdir='/Applications', mustexist=True)
        if not folder:
            return
        destination = Path(folder) / f'{APP_NAME}.app'
        backup_root = Path.home() / 'Library' / 'Application Support' / 'HuginnMuninn' / 'App Backups'
        backup = install_app(source, destination, backup_root)
        message = f'Installed {destination}.\n\nYour settings and scheduled deployment are preserved.'
        if backup:
            message += f'\nPrevious app backed up at:\n{backup}'
        if messagebox.askyesno('Installation complete', message + '\n\nOpen the installed app now?'):
            subprocess.run(['open', '-n', str(destination)], check=True)
    except Exception as error:
        messagebox.showerror('Could not install the app', str(error) + '\n\nIf Applications is not writable, choose a folder you own, such as ~/Applications.')
    finally:
        root.destroy()
