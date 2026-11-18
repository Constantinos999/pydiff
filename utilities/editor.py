"""
Copyright (c) 2026 Constantinos
Part of pydiff - MIT License (see the LICENSE file).

Opening a file in the user's text editor, at a given line where the editor
supports it.

The editor is never chosen through the file's Windows "open" action: for a
.py file that action RUNS the script instead of editing it.
"""

import os
import shutil
import subprocess
import sys


def _windows_candidates():
    bases = [os.environ.get(k) for k in ('ProgramFiles', 'ProgramFiles(x86)', 'ProgramW6432', 'LOCALAPPDATA')]
    found = []
    for base in filter(None, bases):          # Notepad++ first, then VS Code
        found.append(os.path.join(base, 'Notepad++', 'notepad++.exe'))
    for base in filter(None, bases):
        found.append(os.path.join(base, 'Programs', 'Microsoft VS Code', 'Code.exe'))
        found.append(os.path.join(base, 'Microsoft VS Code', 'Code.exe'))
    npp = shutil.which('notepad++')
    if npp:
        found.append(npp)
    code = shutil.which('code')               # ...\Microsoft VS Code\bin\code.cmd
    if code:
        found.append(os.path.join(os.path.dirname(os.path.dirname(code)), 'Code.exe'))
    found.append(os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'notepad.exe'))
    return found


def _other_candidates():
    return [shutil.which(n) for n in ('code', 'gedit', 'gnome-text-editor', 'kate', 'xed', 'mousepad', 'pluma')]


def find_editor(settings):
    """Path of the editor to use, or None."""
    chosen = settings.get('editor')
    if chosen and os.path.isfile(chosen):
        return chosen
    candidates = _windows_candidates() if os.name == 'nt' else _other_candidates()
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def editor_label(settings):
    exe = find_editor(settings)
    if not exe:
        return 'your text editor'
    name = os.path.splitext(os.path.basename(exe))[0].lower()
    return {'notepad++': 'Notepad++', 'code': 'VS Code', 'notepad': 'Notepad'}.get(name, os.path.basename(exe))


def open_in_editor(path, line, settings):
    """Open `path` (at `line`, if the editor supports it). Raises OSError on failure."""
    exe = find_editor(settings)
    line = max(1, int(line or 1))
    if not exe:
        if sys.platform == 'darwin':
            subprocess.Popen(['open', '-t', path])
            return
        raise OSError('No text editor was found. Choose one with File \u2192 Choose Editor\u2026')
    name = os.path.splitext(os.path.basename(exe))[0].lower()
    if name == 'notepad++':
        args = [exe, '-n%d' % line, path]
    elif name == 'code':
        args = [exe, '--goto', '%s:%d' % (path, line)]
    elif name in ('gedit', 'gnome-text-editor', 'kate', 'xed', 'mousepad', 'pluma'):
        args = [exe, '+%d' % line, path]
    else:
        args = [exe, path]                    # e.g. Notepad: no line option
    subprocess.Popen(args, close_fds=True)
