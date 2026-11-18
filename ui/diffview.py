"""
Copyright (c) 2026 Constantinos
Part of pydiff - MIT License (see the LICENSE file).

DiffView: draws a comparison into a MainWindowUI's panes and provides the
toolbar and its features:

  - side-by-side or in-line (single pane) view
  - 'only changes': hide unchanged stretches, keeping a few lines of context
  - previous / next change navigation
  - export to an HTML report or a standard .diff file
  - a status line summarising the differences

Used by both the main window and the function-comparison window.
"""

import difflib
import html
import os
import webbrowser

from utilities.diffengine import (compare_lines, visible_rows, summary,
                                  SAME, CHANGED, LEFT, RIGHT)
from utilities.textfiles import split_lines
try:    # for Python2
    from Tkinter import NORMAL, DISABLED, END, BooleanVar, StringVar, LEFT as PACK_LEFT, RIGHT as PACK_RIGHT, Y
    import ttk
    from tkFileDialog import asksaveasfilename
    from tkMessageBox import askyesno, showinfo, showerror
    from tkSimpleDialog import askinteger
except ImportError:    # for Python3
    from tkinter import NORMAL, DISABLED, END, BooleanVar, StringVar, LEFT as PACK_LEFT, RIGHT as PACK_RIGHT, Y
    from tkinter import ttk
    from tkinter.filedialog import asksaveasfilename
    from tkinter.messagebox import askyesno, showinfo, showerror
    from tkinter.simpledialog import askinteger


class DiffView(object):
    def __init__(self, ui, settings, extra_buttons=()):
        """extra_buttons: [(label, command)] added to the toolbar after the standard ones."""
        self.ui = ui
        self.window = ui.main_window
        self.settings = settings
        self.rows = []
        self.left_lines, self.right_lines = [], []
        self.left_title = self.right_title = ''
        self.notes = []               # extra status info (encodings, line endings)
        self.blocks = []              # [(first display line, last display line)] per change
        self.current = -1             # index into self.blocks of the change jumped to
        self.has_content = False
        self.display_lnos = []

        self.view_var = StringVar(value='inline' if settings.get('inline') else 'side')
        self.only_var = BooleanVar(value=settings.get('only_changes'))
        self.status_var = StringVar(value='')
        self._build_toolbar(extra_buttons)
        self.window.bind('<Alt-Down>', lambda e: self.next_change())
        self.window.bind('<Alt-Up>', lambda e: self.previous_change())
        self.window.bind('<Control-e>', lambda e: self.export())
        self._apply_layout()

    # ------------------------------------------------------------------ toolbar
    def _build_toolbar(self, extra_buttons):
        bar = self.ui.create_toolbar()

        def sep():
            ttk.Separator(bar, orient='vertical').pack(side=PACK_LEFT, fill=Y, padx=6, pady=2)

        ttk.Button(bar, text='▲ Previous', command=self.previous_change).pack(side=PACK_LEFT)
        ttk.Button(bar, text='▼ Next', command=self.next_change).pack(side=PACK_LEFT, padx=(3, 0))
        sep()
        ttk.Radiobutton(bar, text='Side by side', value='side', variable=self.view_var,
                        style='Toolbutton', command=self._view_changed).pack(side=PACK_LEFT)
        ttk.Radiobutton(bar, text='In-line', value='inline', variable=self.view_var,
                        style='Toolbutton', command=self._view_changed).pack(side=PACK_LEFT, padx=(2, 0))
        sep()
        ttk.Checkbutton(bar, text='Only changes', variable=self.only_var,
                        style='Toolbutton', command=self._only_changed).pack(side=PACK_LEFT)
        sep()
        ttk.Button(bar, text='Export…', command=self.export).pack(side=PACK_LEFT)
        for label, command in extra_buttons:
            ttk.Button(bar, text=label, command=command).pack(side=PACK_LEFT, padx=(3, 0))
        ttk.Label(bar, textvariable=self.status_var, anchor='e').pack(side=PACK_RIGHT, padx=(10, 4))

    def view_menu_items(self):
        """Menu entries for the View menu (shared by both windows)."""
        return [
            {'name': 'Side by Side', 'variable': self.view_var, 'value': 'side', 'command': self._view_changed},
            {'name': 'In-line (single pane)', 'variable': self.view_var, 'value': 'inline', 'command': self._view_changed},
            {'separator'},
            {'name': 'Only Show Changes', 'variable': self.only_var, 'command': self._only_changed},
            {'name': 'Lines of Context Around Changes…', 'command': self.ask_context_lines},
            {'separator'},
            {'name': 'Next Change', 'command': self.next_change, 'accelerator': 'Alt+Down'},
            {'name': 'Previous Change', 'command': self.previous_change, 'accelerator': 'Alt+Up'},
        ]

    def _view_changed(self):
        self.settings.set('inline', self.view_var.get() == 'inline')
        self._apply_layout()
        self.redraw()

    def _only_changed(self):
        self.settings.set('only_changes', bool(self.only_var.get()))
        self.redraw()

    def ask_context_lines(self):
        n = askinteger('Lines of context', 'With "Only changes" on, how many unchanged lines\n'
                       'should be kept above and below each change?',
                       initialvalue=self.settings.get('context_lines'), minvalue=0, maxvalue=100,
                       parent=self.window)
        if n is not None:
            self.settings.set('context_lines', n)
            if self.only_var.get():
                self.redraw()

    @property
    def inline(self):
        return self.view_var.get() == 'inline'

    def _apply_layout(self):
        ui = self.ui
        right_widgets = (ui.rightLinenumbers, ui.rightFileTextArea, ui.rightHorizontalScrollbar, ui.rightFileLabel)
        if self.inline:
            for w in right_widgets:
                w.grid_remove()
            self.window.grid_columnconfigure(ui.rightTextAreaCol, weight=0)
        else:
            for w in right_widgets:
                w.grid()
            self.window.grid_columnconfigure(ui.rightTextAreaCol, weight=1)
            if not self.has_content:
                ui.rightLinenumbers.grid_remove()
        self._update_labels()

    def _update_labels(self):
        if self.inline and (self.left_title or self.right_title):
            self.ui.leftFileLabel.config(text='%s   →   %s' % (self.left_title, self.right_title))
        else:
            self.ui.leftFileLabel.config(text=self.left_title)
            self.ui.rightFileLabel.config(text=self.right_title)

    # ------------------------------------------------------------------ content
    def set_titles(self, left_title, right_title):
        self.left_title, self.right_title = left_title, right_title
        self._update_labels()

    def show(self, left_text, right_text, left_numbers=None, right_numbers=None, notes=()):
        """Compare two texts and display the result."""
        self.left_lines, self.right_lines = split_lines(left_text), split_lines(right_text)
        self.rows = compare_lines(self.left_lines, self.right_lines, left_numbers, right_numbers)
        self.notes = list(notes)
        self.has_content = True
        self.current = -1
        self._apply_layout()
        self.redraw()

    def show_message(self, left_message, right_message=None, status=''):
        """Show a message instead of file contents (e.g. for binary files)."""
        self.rows, self.left_lines, self.right_lines, self.blocks = [], [], [], []
        self.has_content = False
        self.current = -1
        self._apply_layout()
        ui = self.ui
        for area, msg in ((ui.leftFileTextArea, left_message),
                          (ui.rightFileTextArea, left_message if right_message is None else right_message)):
            area.config(state=NORMAL, background=ui.whiteColor if msg else ui.grayColor)
            area.delete(1.0, END)
            if msg:
                area.insert('1.0', msg, 'message')
            area.config(state=DISABLED)
        for nums in (ui.leftLinenumbers, ui.rightLinenumbers):
            nums.grid_remove()
        self.status_var.set(status)

    def clear(self):
        self.set_titles('', '')
        self.show_message('', '', '')

    def redraw(self):
        if not self.has_content:
            return
        ui = self.ui
        context = self.settings.get('context_lines') if self.only_var.get() else None
        items = visible_rows(self.rows, context)
        if self.inline:
            panes = self._layout_inline(items)
        else:
            panes = self._layout_side(items)
        self._fill(panes)
        self._update_status()
        for area in (ui.leftFileTextArea, ui.rightFileTextArea):
            area.config(background=ui.whiteColor)
        ui.leftLinenumbers.grid()
        if not self.inline:
            ui.rightLinenumbers.grid()

    # Each layout returns, per widget: (list of lines, [(tag, line, col_from, col_to or None)])
    # col_to None = to the end of the line, including the newline so the
    # colour fills the full width of the pane.
    def _layout_side(self, items):
        L, R, LN, RN = [], [], [], []
        lt, rt, lnt, rnt = [], [], [], []
        kinds = []
        for item in items:
            n = len(L) + 1
            if isinstance(item, int):
                msg = '⋯  %d unchanged line%s hidden  ⋯' % (item, '' if item == 1 else 's')
                L.append(msg); R.append(msg); LN.append(''); RN.append('')
                for t, nt in ((lt, lnt), (rt, rnt)):
                    t.append(('fold', n, 0, None)); nt.append(('fold', n, 0, None))
                kinds.append('fold')
                continue
            r = item
            L.append(r.left if r.left is not None else '')
            R.append(r.right if r.right is not None else '')
            LN.append(str(r.lno) if r.lno is not None else '')
            RN.append(str(r.rno) if r.rno is not None else '')
            kinds.append(r.kind)
            if r.kind == CHANGED:
                lt.append(('red', n, 0, None)); rt.append(('green', n, 0, None))
                lt += [('darkred', n, a, b) for a, b in r.lchg]
                rt += [('darkgreen', n, a, b) for a, b in r.rchg]
            elif r.kind == LEFT:
                lt.append(('red', n, 0, None)); rt.append(('gray', n, 0, None))
            elif r.kind == RIGHT:
                lt.append(('gray', n, 0, None)); rt.append(('green', n, 0, None))
        self.display_lnos = [int(x) if x else None for x in LN]
        self._set_blocks(kinds)
        return [(self.ui.leftFileTextArea, L, lt), (self.ui.rightFileTextArea, R, rt),
                (self.ui.leftLinenumbers, LN, lnt), (self.ui.rightLinenumbers, RN, rnt)]

    def _layout_inline(self, items):
        T, N, tt, nt, kinds = [], [], [], [], []
        lnos = self.display_lnos = []
        width = max([len(str(r.lno or '')) for r in self.rows] + [len(str(r.rno or '')) for r in self.rows] + [1])

        def gutter(l, r, sym):
            return '%*s %*s %s' % (width, l if l is not None else '', width, r if r is not None else '', sym)

        # within each run of changes, list all removed lines first, then all
        # added lines (as GitHub does) rather than alternating line by line
        grouped, run = [], []
        for item in items:
            if not isinstance(item, int) and item.kind != SAME:
                run.append(item)
                continue
            grouped += [('old', r) for r in run if r.left is not None]
            grouped += [('new', r) for r in run if r.right is not None]
            run = []
            grouped.append(item)
        grouped += [('old', r) for r in run if r.left is not None]
        grouped += [('new', r) for r in run if r.right is not None]

        for item in grouped:
            n = len(T) + 1
            if isinstance(item, int):
                T.append(u'\u22ef  %d unchanged line%s hidden  \u22ef' % (item, '' if item == 1 else 's'))
                N.append('')
                lnos.append(None)
                tt.append(('fold', n, 0, None)); nt.append(('fold', n, 0, None))
                kinds.append('fold')
            elif not isinstance(item, tuple):
                T.append(item.left); N.append(gutter(item.lno, item.rno, ' ')); kinds.append(SAME)
                lnos.append(item.lno)
            elif item[0] == 'old':
                r = item[1]
                T.append(r.left); N.append(gutter(r.lno, None, '-')); kinds.append(r.kind)
                lnos.append(r.lno)
                tt.append(('red', n, 0, None)); nt.append(('red', n, 0, None))
                tt += [('darkred', n, a, b) for a, b in r.lchg]
            else:
                r = item[1]
                T.append(r.right); N.append(gutter(None, r.rno, '+')); kinds.append(r.kind)
                lnos.append(None)
                tt.append(('green', n, 0, None)); nt.append(('green', n, 0, None))
                tt += [('darkgreen', n, a, b) for a, b in r.rchg]
        self._set_blocks(kinds)
        return [(self.ui.leftFileTextArea, T, tt), (self.ui.leftLinenumbers, N, nt),
                (self.ui.rightFileTextArea, [], []), (self.ui.rightLinenumbers, [], [])]

    def _set_blocks(self, kinds):
        self.blocks, start = [], None
        for i, k in enumerate(kinds, 1):
            if k not in (SAME, 'fold'):
                if start is None:
                    start = i
            elif start is not None:
                self.blocks.append((start, i - 1))
                start = None
        if start is not None:
            self.blocks.append((start, len(kinds)))
        self.current = -1

    def _fill(self, panes):
        """Insert all text in one go, then apply colour tags: much faster than
        inserting line by line, character by character."""
        widest = 1
        for widget, lines, tags in panes:
            widget.config(state=NORMAL)
            widget.delete(1.0, END)
            widget.insert('1.0', '\n'.join(lines) + ('\n' if lines else ''))
            for tag, line, a, b in tags:
                if b is None:
                    widget.tag_add(tag, '%d.%d' % (line, a), '%d.0' % (line + 1))
                else:
                    widget.tag_add(tag, '%d.%d' % (line, a), '%d.%d' % (line, b))
            if widget in (self.ui.leftLinenumbers, self.ui.rightLinenumbers):
                widest = max([widest] + [len(l) for l in lines])
            widget.config(state=DISABLED)
        for nums in (self.ui.leftLinenumbers, self.ui.rightLinenumbers):
            nums.config(width=widest + 1)
            nums.tag_add('line', '1.0', END)

    def _update_status(self):
        nblocks, removed, added, changed = summary(self.rows)
        if not nblocks:
            text = 'No differences'
        else:
            parts = []
            if changed:
                parts.append('%d edited' % changed)
            if removed:
                parts.append('%d removed' % removed)
            if added:
                parts.append('%d added' % added)
            text = '%d change%s  (lines: %s)' % (nblocks, '' if nblocks == 1 else 's', ', '.join(parts))
        if self.current >= 0 and self.blocks:
            text = 'Change %d of %d  ·  ' % (self.current + 1, len(self.blocks)) + text
        for note in self.notes:
            text += '  ·  ' + note
        self.status_var.set(text)

    # ------------------------------------------------------------------ navigation
    def _top_line(self):
        return int(self.ui.leftFileTextArea.index('@0,0').split('.')[0])

    def next_change(self):
        if not self.blocks:
            return
        if self.current >= 0:
            target = min(self.current + 1, len(self.blocks) - 1)
        else:
            top = self._top_line()
            later = [i for i, (a, b) in enumerate(self.blocks) if a > top]
            target = later[0] if later else len(self.blocks) - 1
            if top <= 1 and self.blocks[0][0] <= 3:
                target = 0
        self.go_to_change(target)

    def previous_change(self):
        if not self.blocks:
            return
        if self.current >= 0:
            target = max(self.current - 1, 0)
        else:
            top = self._top_line()
            earlier = [i for i, (a, b) in enumerate(self.blocks) if a < top]
            target = earlier[-1] if earlier else 0
        self.go_to_change(target)

    def go_to_change(self, index):
        ui = self.ui
        self.current = index
        start, end = self.blocks[index]
        for nums in (ui.leftLinenumbers, ui.rightLinenumbers):
            nums.tag_remove('current', '1.0', END)
            nums.tag_add('current', '%d.0' % start, '%d.0' % (end + 1))
        self.scroll_to_line(start)
        self._update_status()

    def scroll_to_line(self, line):
        """Scroll so display line `line` is a few lines below the top."""
        total = int(self.ui.leftFileTextArea.index('end-1c').split('.')[0]) or 1
        self.ui.scrollBothY('moveto', max(0.0, (line - 4) / float(total)))

    def display_line_for(self, left_line_number):
        """Display line showing (or nearest after) the given real left line number."""
        last = None
        for i, n in enumerate(getattr(self, 'display_lnos', []), 1):
            if n is None:
                continue
            if n >= left_line_number:
                return i
            last = i
        return last

    # ------------------------------------------------------------------ export
    def export(self):
        if not self.has_content:
            showinfo('Export', 'Compare two files first, then export the result.', parent=self.window)
            return
        base = '%s_vs_%s' % (_stem(self.left_title), _stem(self.right_title))
        path = asksaveasfilename(parent=self.window, title='Export comparison',
                                 initialfile=base + '.html', defaultextension='.html',
                                 filetypes=[('HTML report (opens in any web browser)', '*.html'),
                                            ('Unified diff / patch file', '*.diff *.patch'),
                                            ('All files', '*.*')])
        if not path:
            return
        try:
            if path.lower().endswith(('.diff', '.patch', '.txt')):
                content = self.unified_diff()
            else:
                content = self.html_report()
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(content)
        except Exception as e:
            showerror('Export', 'Could not save the file:\n%s' % e, parent=self.window)
            return
        if path.lower().endswith(('.html', '.htm')):
            if askyesno('Export', 'Report saved:\n%s\n\nOpen it in your web browser now?' % path,
                        parent=self.window):
                webbrowser.open('file:///' + os.path.abspath(path).replace('\\', '/'))
        else:
            showinfo('Export', 'Saved:\n%s' % path, parent=self.window)

    def unified_diff(self):
        n = self.settings.get('context_lines') if self.only_var.get() else 3
        lines = difflib.unified_diff(self.left_lines, self.right_lines,
                                     fromfile=self.left_title or 'left', tofile=self.right_title or 'right',
                                     n=n, lineterm='')
        out = '\n'.join(lines)
        return out + '\n' if out else ''

    def html_report(self):
        """A self-contained HTML page mirroring the current view."""
        context = self.settings.get('context_lines') if self.only_var.get() else None
        items = visible_rows(self.rows, context)
        esc = html.escape

        def marked(text, ranges, cls):
            if text is None:
                return ''
            out, pos = [], 0
            for a, b in ranges:
                out.append(esc(text[pos:a]))
                out.append('<span class="%s">%s</span>' % (cls, esc(text[a:b])))
                pos = b
            out.append(esc(text[pos:]))
            return ''.join(out)

        body = []
        if self.inline:
            body.append('<table class="diff inline"><colgroup><col class="n"><col class="n"><col></colgroup>')
            run = []

            def flush():
                for it in run:
                    if it.left is not None:
                        body.append('<tr class="del"><td class="n">%s</td><td class="n"></td><td>%s</td></tr>'
                                    % (it.lno, marked(it.left, it.lchg, 'x')))
                for it in run:
                    if it.right is not None:
                        body.append('<tr class="add"><td class="n"></td><td class="n">%s</td><td>%s</td></tr>'
                                    % (it.rno, marked(it.right, it.rchg, 'x')))
                del run[:]

            for it in items:
                if not isinstance(it, int) and it.kind != SAME:
                    run.append(it)
                    continue
                flush()
                if isinstance(it, int):
                    body.append('<tr class="fold"><td colspan="3">&#8943; %d unchanged lines hidden &#8943;</td></tr>' % it)
                else:
                    body.append('<tr><td class="n">%s</td><td class="n">%s</td><td>%s</td></tr>'
                                % (it.lno, it.rno, esc(it.left)))
            flush()
        else:
            body.append('<table class="diff side"><colgroup><col class="n"><col class="t"><col class="n"><col class="t"></colgroup>')
            body.append('<tr><th></th><th>%s</th><th></th><th>%s</th></tr>' % (esc(self.left_title), esc(self.right_title)))
            for it in items:
                if isinstance(it, int):
                    body.append('<tr class="fold"><td colspan="4">&#8943; %d unchanged lines hidden &#8943;</td></tr>' % it)
                    continue
                lcls = {CHANGED: 'del', LEFT: 'del', RIGHT: 'pad'}.get(it.kind, '')
                rcls = {CHANGED: 'add', RIGHT: 'add', LEFT: 'pad'}.get(it.kind, '')
                body.append('<tr><td class="n">%s</td><td class="%s">%s</td><td class="n">%s</td><td class="%s">%s</td></tr>'
                            % (it.lno or '', lcls, marked(it.left, it.lchg, 'x'),
                               it.rno or '', rcls, marked(it.right, it.rchg, 'x')))
        body.append('</table>')
        nblocks = summary(self.rows)[0]
        return HTML_PAGE % {
            'title': esc('%s vs %s' % (self.left_title, self.right_title)),
            'left': esc(self.left_title), 'right': esc(self.right_title),
            'status': esc(self.status_var.get() if nblocks else 'No differences'),
            'table': '\n'.join(body),
        }


def _stem(path):
    name = os.path.splitext(os.path.basename(path or 'file'))[0]
    return ''.join(c if c.isalnum() or c in '-_.' else '_' for c in name) or 'file'


HTML_PAGE = '''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>pydiff: %(title)s</title>
<style>
 body { font-family: system-ui, Segoe UI, sans-serif; margin: 24px; color: #222; }
 h1 { font-size: 18px; margin: 0 0 4px; }
 .files { font-family: Consolas, monospace; font-size: 13px; color: #444; }
 .status { margin: 8px 0 16px; color: #555; font-size: 14px; }
 table.diff { border-collapse: collapse; width: 100%%; table-layout: fixed;
   font-family: Consolas, Menlo, monospace; font-size: 13px; }
 table.diff td { padding: 1px 6px; white-space: pre-wrap; word-break: break-all; vertical-align: top; }
 table.diff th { text-align: left; font-family: Consolas, monospace; font-size: 12px; padding: 4px 6px;
   background: #eee; border-bottom: 1px solid #ccc; }
 col.n { width: 4.5em; } td.n { color: #888; text-align: right; background: #f6f6f6; user-select: none; }
 td.del, tr.del td:not(.n) { background: #ffdcdc; } td.add, tr.add td:not(.n) { background: #d9f7df; }
 td.del .x, tr.del .x { background: #f28b8b; font-weight: bold; }
 td.add .x, tr.add .x { background: #7fd893; font-weight: bold; }
 td.pad { background: #e6e6e6; }
 tr.fold td { background: #eef1f6; color: #5a6578; text-align: center; font-family: system-ui, sans-serif; }
 .foot { margin-top: 16px; font-size: 12px; color: #888; }
</style></head><body>
<h1>File comparison</h1>
<div class="files">Left: %(left)s<br>Right: %(right)s</div>
<div class="status">%(status)s</div>
%(table)s
<div class="foot">Generated by pydiff</div>
</body></html>
'''
