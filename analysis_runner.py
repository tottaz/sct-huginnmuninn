"""Standalone worker entry point, bundled separately from the desktop editor."""
from pathlib import Path
import runpy
import sys
# Explicit imports let PyInstaller discover analysis dependencies.
import requests
import bs4
import news_scraper
# Importing the analysis module is side-effect free. This lets the packager track
# every dependency used by the deployed script loaded through runpy below.
import daily_news_analysis

if __name__ == '__main__':
    if '--self-test' in sys.argv:
        print('Analysis runtime OK')
    else:
        directory = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
        script = directory / 'sct_daily_news_analysis.py'
        runpy.run_path(str(script), run_name='__main__')
