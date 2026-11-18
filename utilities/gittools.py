"""
Copyright (c) 2026 Constantinos
Part of pydiff - MIT License (see the LICENSE file).

Git integration:
  - get a file as it was in a commit (to compare with the current version)
  - set pydiff up as git's diff viewer ("git difftool")
"""

import os
import shutil
import subprocess
import sys
import tempfile


class GitError(Exception):
    pass


def _git(args, cwd):
    if not shutil.which('git'):
        raise GitError('Git is not installed (or not on the PATH).\n'
                       'Get it from https://git-scm.com/downloads')
    flags = 0x08000000 if os.name == 'nt' else 0      # CREATE_NO_WINDOW: no flashing console
    p = subprocess.run(['git'] + args, cwd=cwd, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, creationflags=flags)
    if p.returncode != 0:
        raise GitError(p.stderr.decode('utf-8', 'replace').strip() or 'git %s failed' % args[0])
    return p.stdout


def repo_root(path):
    folder = path if os.path.isdir(path) else os.path.dirname(os.path.abspath(path))
    try:
        return _git(['rev-parse', '--show-toplevel'], folder).decode('utf-8').strip()
    except GitError as e:
        if 'not a git repository' in str(e).lower():
            raise GitError('This file is not inside a git repository:\n%s' % path)
        raise


def file_at_commit(path, ref='HEAD'):
    """Save the committed version of `path` to a temporary file.
    Returns (temp file path, short commit id)."""
    path = os.path.abspath(path)
    root = repo_root(path)
    rel = os.path.relpath(path, root).replace('\\', '/')
    folder = os.path.dirname(path)
    try:
        short = _git(['rev-parse', '--short', ref + '^{commit}'], folder).decode().strip()
    except GitError:
        raise GitError('"%s" is not a commit, branch or tag in this repository.' % ref)
    try:
        data = _git(['show', '%s:%s' % (short, rel)], root)
    except GitError:
        raise GitError('"%s" does not exist in commit %s\n'
                       '(it may be new and not committed yet).' % (rel, short))
    stem, ext = os.path.splitext(os.path.basename(path))
    out_dir = os.path.join(tempfile.gettempdir(), 'pydiff_git')
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, '%s [%s]%s' % (stem, short, ext))
    with open(out, 'wb') as f:
        f.write(data)
    return out, short


def pydiff_command(script_path):
    """The command git should run, with forward slashes (git runs it through sh)."""
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), 'pythonw.exe')
    if os.path.isfile(pyw):
        exe = pyw
    fwd = lambda p: p.replace('\\', '/')
    return '"%s" "%s" "$LOCAL" "$REMOTE"' % (fwd(exe), fwd(os.path.abspath(script_path)))


def setup_difftool(script_path, make_default=True):
    """Register pydiff with git (for the current user, all repositories)."""
    cwd = os.path.expanduser('~')
    _git(['config', '--global', 'difftool.pydiff.cmd', pydiff_command(script_path)], cwd)
    _git(['config', '--global', 'difftool.prompt', 'false'], cwd)
    if make_default:
        _git(['config', '--global', 'diff.tool', 'pydiff'], cwd)
