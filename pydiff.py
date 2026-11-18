#!/usr/bin/env python3
"""
MIT License

Copyright (c) 2016 Yasser Elsayed
Copyright (c) 2026 Constantinos (modifications and additions - see CHANGES.md)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

-------------------------------------------------------------------------------
pydiff - side-by-side GUI diff of two files (or two folders).

Usage:
    python pydiff.py                      open empty, use File menu
    python pydiff.py left.py right.py     compare two files straight away
    python pydiff.py -p left.py right.py  same (original syntax)
    python pydiff.py -f left.py right.py  also open the function-by-function view
    python pydiff.py --check-deps         only check/install dependencies

On start-up it checks its own dependencies and installs anything missing that
pip can install. It needs only the Python standard library plus Tkinter, which
ships with the normal python.org Windows installer.
"""

import os
import sys
import argparse
import subprocess
import traceback
import importlib.util

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ERROR_LOG = os.path.join(APP_DIR, 'pydiff_error.log')

# Third-party packages pydiff needs, as {import name: pip package name}.
# pydiff currently needs none; this list is here so that if a dependency is
# ever added, it is installed automatically the first time it is missing.
PIP_PACKAGES = {}


# --------------------------------------------------------------------------
# Messages that work with or without a console (pythonw has no console)
# --------------------------------------------------------------------------
def _has_console():
    try:
        return sys.stdout is not None and sys.stdout.isatty()
    except Exception:
        return False


def report(title, message, error=True):
    """Show a message in the console if there is one, otherwise in a popup."""
    if _has_console():
        print(('ERROR: ' if error else '') + title + '\n' + message)
        return
    try:
        from tkinter import Tk, messagebox
        root = Tk()
        root.withdraw()
        (messagebox.showerror if error else messagebox.showinfo)(title, message)
        root.destroy()
        return
    except Exception:
        pass
    if os.name == 'nt':   # no Tkinter at all: fall back to a native Windows box
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10 if error else 0x40)
            return
        except Exception:
            pass
    if sys.stderr:
        sys.stderr.write(title + '\n' + message + '\n')


# --------------------------------------------------------------------------
# Dependency checks
# --------------------------------------------------------------------------
def _installed(import_name):
    try:
        return importlib.util.find_spec(import_name) is not None
    except (ImportError, ValueError):
        return False


def _pip_install(packages):
    cmd = [sys.executable, '-m', 'pip', 'install', '--user', '--disable-pip-version-check'] + packages
    print('Installing missing packages: ' + ', '.join(packages))
    if subprocess.call(cmd) == 0:
        return True
    # pip itself may be missing; ensurepip ships with Python, then retry once
    subprocess.call([sys.executable, '-m', 'ensurepip', '--user'])
    return subprocess.call(cmd) == 0


def check_dependencies():
    """Return True if everything pydiff needs is available, installing what it can."""
    if sys.version_info < (3, 8):
        report('Python too old',
               'pydiff needs Python 3.8 or newer; this is Python %d.%d.\n'
               'Install a current Python from https://www.python.org/downloads/'
               % sys.version_info[:2])
        return False

    # 1. Tkinter (the GUI toolkit). Part of Python itself, so pip cannot install it.
    if not _installed('tkinter'):
        report('Tkinter is missing',
               'Your Python installation was set up without Tkinter (the GUI library).\n\n'
               'Fix: run the Python installer again, choose "Modify", tick '
               '"tcl/tk and IDLE", and finish. Then start pydiff again.')
        return False

    # 2. pydiff's own files (catches an incomplete download or copy).
    for part in (('ui', 'mainwindow.py'), ('ui', 'diffview.py'), ('ui', 'functioncompare.py'),
                 ('utilities', 'difflibparser.py')):
        if not os.path.isfile(os.path.join(APP_DIR, *part)):
            report('pydiff is incomplete',
                   'This file is missing:\n%s\n\nPlease download pydiff again.'
                   % os.path.join(APP_DIR, *part))
            return False

    # 3. Any third-party pip packages (none at present).
    missing = [pip for mod, pip in PIP_PACKAGES.items() if not _installed(mod)]
    if missing:
        if not _pip_install(missing):
            report('Could not install packages',
                   'pip failed to install: ' + ', '.join(missing) +
                   '\nCheck your internet connection and try again.')
            return False
        importlib.invalidate_caches()
    return True


# --------------------------------------------------------------------------
# Start-up
# --------------------------------------------------------------------------
def _enable_sharp_text_on_windows():
    """Without this, Tk windows look blurry on scaled (high-DPI) Windows displays."""
    if os.name != 'nt':
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _log_crash(exc_type, exc, tb):
    text = ''.join(traceback.format_exception(exc_type, exc, tb))
    try:
        with open(ERROR_LOG, 'a', encoding='utf-8') as f:
            f.write(text + '\n')
    except Exception:
        pass
    report('pydiff crashed', text[-1500:] + '\n\n(Details saved to %s)' % ERROR_LOG)


def parse_args():
    parser = argparse.ArgumentParser(description="pydiff - Tkinter GUI tool based on Python's difflib")
    parser.add_argument('-p', '--paths', metavar=('path1', 'path2'), nargs=2,
                        help='Two paths to compare (files or directories)')
    parser.add_argument('files', nargs='*', help='Two paths to compare (same as -p)')
    parser.add_argument('-f', '--functions', action='store_true',
                        help='Also open the function-by-function comparison (Python files)')
    parser.add_argument('--check-deps', action='store_true',
                        help='Only check / install dependencies, then exit')
    args = parser.parse_args()

    paths = args.paths or args.files
    if len(paths) not in (0, 2):
        parser.error('give exactly two paths to compare (you gave %d)' % len(paths))
    return args, paths


def main():
    # Make the bundled packages (ui, utilities) importable no
    # matter which folder pydiff was launched from.
    if APP_DIR not in sys.path:
        sys.path.insert(0, APP_DIR)

    args, paths = parse_args()

    if not check_dependencies():
        return 1
    if args.check_deps:
        print('All pydiff dependencies are available.')
        return 0

    leftpath = rightpath = None
    if paths:
        leftpath, rightpath = [os.path.abspath(p) for p in paths]
        bad = [p for p in (leftpath, rightpath) if not os.path.exists(p)]
        if bad:
            report('Path not found', 'These paths do not exist:\n' + '\n'.join(bad))
            return 1

    _enable_sharp_text_on_windows()
    sys.excepthook = _log_crash
    import tkinter
    # errors inside button/menu callbacks: show them instead of failing silently
    tkinter.Tk.report_callback_exception = lambda self, *exc: _log_crash(*exc)

    from ui.mainwindow import MainWindow
    MainWindow().start(leftpath, rightpath, functions=args.functions)
    return 0


if __name__ == '__main__':
    sys.exit(main())
