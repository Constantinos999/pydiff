"""
Copyright (c) 2026 Constantinos
Part of pydiff - MIT License (see the LICENSE file).

Compare two Python files function by function.

Each file is parsed with Python's own parser (the standard `ast` module), and
every function, class and method is matched up by name - so the comparison
works even when functions have been moved around or reordered. Each one is
classed as:

    same               identical text
    comments/spacing   only comments, blank lines or spacing differ
    changed            the code itself differs
    renamed            same code under a different name
    left only / right only

Picking an entry in the list shows the diff of just that piece, with its real
line numbers from each file.
"""

import ast
import io
import re
import textwrap
import tokenize

from ui.mainwindow_ui import MainWindowUI
from ui.diffview import render_diff
try:    # for Python2
    from Tkinter import Toplevel, W
except ImportError:    # for Python3
    from tkinter import Toplevel, W

MODULE_CODE = '(module-level code)'
WHOLE_FILE = '(whole file)'

SAME, FORMAT, CHANGED, RENAMED, LEFT_ONLY, RIGHT_ONLY = (
    'same', 'comments/spacing', 'changed', 'renamed', 'left only', 'right only')

STATUS_TAG = {SAME: (), FORMAT: ('blue',), CHANGED: ('yellow',), RENAMED: ('purpleLight',),
              LEFT_ONLY: ('red',), RIGHT_ONLY: ('green',)}


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
class Definition(object):
    """One function / class / method (or the module-level code) of a file."""

    def __init__(self, name, short_name, kind, linenos, all_lines, span=None):
        self.name = name                # e.g. 'MyClass.run()'
        self.short_name = short_name    # e.g. 'run'
        self.kind = kind                # 'def', 'class' or 'module'
        self.linenos = linenos          # real line numbers this piece covers
        self._span = span               # (first, last) line in the file, if not linenos
        self.text = '\n'.join(all_lines[i - 1] for i in linenos)
        self.exact = '\n'.join(l.rstrip() for l in self.text.splitlines()).strip('\n')
        self.norm = normalise(self.text)
        # code with its own name blanked out, for spotting renamed functions
        blanked = re.sub(r'\b%s\b' % re.escape(short_name), '_', self.text, count=1) if short_name else self.text
        self.norm_unnamed = normalise(blanked)

    @property
    def span(self):
        if self._span:
            return '%d-%d' % self._span
        if not self.linenos:
            return ''
        return '%d-%d' % (self.linenos[0], self.linenos[-1])


def normalise(text):
    """Code as a sequence of tokens with comments, blank lines and spacing removed."""
    src = textwrap.dedent(text)
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src + '\n').readline):
            if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.ENDMARKER):
                continue
            if tok.type == tokenize.INDENT:
                out.append('<indent>')
            elif tok.type == tokenize.DEDENT:
                out.append('<dedent>')
            elif tok.type == tokenize.NEWLINE:
                out.append('\n')
            else:
                out.append(tok.string)
        return ' '.join(out)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # fall back to a rough line-based clean-up
        lines = (' '.join(l.split('#', 1)[0].split()) for l in src.splitlines())
        return '\n'.join(l for l in lines if l)


def extract_definitions(source):
    """Return [Definition] for the module code, every class, function and method."""
    tree = ast.parse(source)
    lines = source.splitlines()
    defs = []
    seen = {}

    def unique(name):
        seen[name] = seen.get(name, 0) + 1
        return name if seen[name] == 1 else '%s [%d]' % (name, seen[name])

    def walk(body, prefix):
        """Record defs found in body; return the line ranges they occupy."""
        ranges = []
        for node in body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            end = node.end_lineno
            ranges.append((start, end))
            if isinstance(node, ast.ClassDef):
                name = unique(prefix + node.name)
                inner = walk(node.body, name + '.')
                # the class itself = its lines minus its methods (they get their own entries)
                keep = [i for i in range(start, end + 1)
                        if lines[i - 1].strip() and not any(a <= i <= b for a, b in inner)]
                defs.append(Definition('class ' + name, node.name, 'class', keep, lines, (start, end)))
            else:
                name = unique(prefix + node.name + '()')
                defs.append(Definition(name, node.name, 'def', list(range(start, end + 1)), lines))
        return ranges

    top = walk(tree.body, '')
    rest = [i for i in range(1, len(lines) + 1)
            if not any(a <= i <= b for a, b in top) and lines[i - 1].strip()]
    defs.append(Definition(MODULE_CODE, '', 'module', rest, lines))
    defs.sort(key=lambda d: (d.kind != 'module', d.linenos[0] if d.linenos else 0))
    return defs


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------
def compare_definitions(left_defs, right_defs):
    """Return a list of (display name, status, left Definition or None, right Definition or None)."""
    left = dict((d.name, d) for d in left_defs)
    right = dict((d.name, d) for d in right_defs)

    rows = []
    for d in left_defs:
        r = right.get(d.name)
        if r is None:
            rows.append([d.name, LEFT_ONLY, d, None])
        elif d.exact == r.exact:
            rows.append([d.name, SAME, d, r])
        elif d.norm == r.norm:
            rows.append([d.name, FORMAT, d, r])
        else:
            rows.append([d.name, CHANGED, d, r])
    rows += [[d.name, RIGHT_ONLY, None, d] for d in right_defs if d.name not in left]

    # pair up a 'left only' and a 'right only' that have the same code -> renamed
    right_only = [row for row in rows if row[1] == RIGHT_ONLY]
    for row in rows:
        if row[1] != LEFT_ONLY or row[2].kind == 'module':
            continue
        for other in right_only:
            r = other[3]
            if r.kind == row[2].kind and r.norm_unnamed == row[2].norm_unnamed:
                row[0] = '%s  ->  %s' % (row[2].name, r.name)
                row[1], row[3] = RENAMED, r
                rows.remove(other)
                right_only.remove(other)
                break
    return [tuple(r) for r in rows]


# --------------------------------------------------------------------------
# Window
# --------------------------------------------------------------------------
class FunctionCompareWindow(object):
    def __init__(self, parent, left_path, right_path, left_source, right_source):
        self.left_source, self.right_source = left_source, right_source
        self.rows = compare_definitions(extract_definitions(left_source), extract_definitions(right_source))
        self.hide_same = False

        self.window = Toplevel(parent)
        ui = self.ui = MainWindowUI(self.window)
        ui.center_window()
        ui.create_file_path_labels()
        ui.create_text_areas()
        ui.create_line_numbers()
        ui.create_scroll_bars()
        ui.create_file_treeview()
        ui.leftFileTextArea.config(background=ui.whiteColor)
        ui.rightFileTextArea.config(background=ui.whiteColor)
        ui.leftFileLabel.config(text=left_path)
        ui.rightFileLabel.config(text=right_path)
        ui.add_menu('View', [
            {'name': 'Show only differences', 'command': lambda: self.set_hide_same(True)},
            {'name': 'Show everything', 'command': lambda: self.set_hide_same(False)},
            {'separator'},
            {'name': 'Close', 'command': self.window.destroy, 'accelerator': 'Esc'},
        ])
        self.window.bind('<Escape>', lambda *x: self.window.destroy())

        tv = self.tree = ui.fileTreeView
        tv['columns'] = ('status', 'left', 'right')
        tv.heading('#0', text='Function / class', anchor=W)
        tv.heading('status', text='Status', anchor=W)
        tv.heading('left', text='Left lines', anchor=W)
        tv.heading('right', text='Right lines', anchor=W)
        tv.column('#0', width=260)
        tv.column('status', width=135, stretch=False)
        tv.column('left', width=70, stretch=False)
        tv.column('right', width=70, stretch=False)
        tv.tag_configure('blue', background='#d6ecff')
        tv.grid()
        ui.fileTreeYScrollbar.grid()
        ui.fileTreeXScrollbar.grid()
        tv.bind('<<TreeviewSelect>>', lambda *x: self.show_selected())

        self.fill_tree()
        counts = {}
        for row in self.rows:
            counts[row[1]] = counts.get(row[1], 0) + 1
        summary = ', '.join('%d %s' % (counts[s], s) for s in
                            (CHANGED, RENAMED, LEFT_ONLY, RIGHT_ONLY, FORMAT, SAME) if counts.get(s))
        self.window.title('Pydiff - function comparison: ' + summary)

        # open on the first difference, if there is one
        first = next((iid for iid in tv.get_children() if tv.set(iid, 'status') not in ('', SAME)), None)
        tv.selection_set(first or tv.get_children()[0])
        self.window.focus_set()

    def fill_tree(self):
        tv = self.tree
        tv.delete(*tv.get_children())
        self.items = {}
        iid = tv.insert('', 'end', text=WHOLE_FILE, values=('', '', ''))
        self.items[iid] = None
        for row in self.rows:
            name, status, l, r = row
            if self.hide_same and status == SAME:
                continue
            iid = tv.insert('', 'end', text=name, tags=STATUS_TAG[status],
                            values=(status, l.span if l else '', r.span if r else ''))
            self.items[iid] = row

    def set_hide_same(self, value):
        self.hide_same = value
        self.fill_tree()

    def show_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        row = self.items.get(sel[0])
        if row is None:
            render_diff(self.ui, self.left_source, self.right_source)
            return
        _, _, l, r = row
        render_diff(self.ui, l.text if l else '', r.text if r else '',
                    l.linenos if l else None, r.linenos if r else None)


def open_function_compare(parent, left_path, right_path, read_file, showerror):
    """Read both files and open the comparison window; report problems nicely."""
    sources = []
    for path in (left_path, right_path):
        try:
            text = read_file(path)
            ast.parse(text)
        except SyntaxError as e:
            showerror('Compare Functions',
                      'Could not parse this file as Python 3 code:\n%s\n\nLine %s: %s\n\n'
                      '(Files written for Python 2, or that are not Python at all, '
                      'cannot be compared by function. Use the normal comparison instead.)'
                      % (path, e.lineno, e.msg))
            return None
        except Exception as e:
            showerror('Compare Functions', 'Could not read file:\n%s\n%s' % (path, e))
            return None
        sources.append(text)
    return FunctionCompareWindow(parent, left_path, right_path, sources[0], sources[1])
