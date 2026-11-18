"""
Copyright (c) 2026 Constantinos
Part of pydiff - MIT License (see the LICENSE file).

Remembers the user's choices (view mode, start maximised ...) between runs,
in a small file in their home folder: ~/.pydiff_settings.json
"""

import json
import os

PATH = os.path.join(os.path.expanduser('~'), '.pydiff_settings.json')

DEFAULTS = {
    'inline': False,               # in-line (single pane) view instead of side by side
    'only_changes': False,         # hide unchanged lines
    'context_lines': 3,            # unchanged lines kept around each change
    'start_maximised': False,
    'ignore_line_endings': True,   # folder view: files differing only in CRLF/LF aren't 'changed'
}


class Settings(object):
    def __init__(self, path=PATH):
        self.path = path
        self.values = dict(DEFAULTS)
        try:
            with open(path, encoding='utf-8') as f:
                stored = json.load(f)
            for k, v in stored.items():
                if k in DEFAULTS and isinstance(v, type(DEFAULTS[k])):
                    self.values[k] = v
        except (OSError, ValueError):
            pass

    def get(self, key):
        return self.values.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.values[key] = value
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.values, f, indent=2)
        except OSError:
            pass    # not being able to save a preference is never fatal
