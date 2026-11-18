"""
Copyright (c) 2026 Constantinos
Part of pydiff - MIT License (see the LICENSE file).

Shared code that draws a side-by-side diff into a MainWindowUI's two text
panes, with highlighting and line numbers. Used by the main window (whole
files) and by the function-comparison window (one function at a time).
"""

from difflibparser.difflibparser import DifflibParser, DiffCode
try:    # for Python2
    from Tkinter import NORMAL, DISABLED, END
except ImportError:    # for Python3
    from tkinter import NORMAL, DISABLED, END


def render_diff(ui, left_text, right_text, left_linenos=None, right_linenos=None):
    """Diff left_text against right_text and show the result in ui's panes.

    left_linenos / right_linenos: optional list of the real line number of
    each line (for showing a piece of a file with its true line numbers).
    Defaults to 1, 2, 3, ...
    """
    left_lines = left_text.splitlines()
    right_lines = right_text.splitlines()

    def label(numbers, i):
        if numbers is not None and i - 1 < len(numbers):
            return str(numbers[i - 1])
        return str(i)

    diff = DifflibParser(left_lines, right_lines)

    widgets = (ui.leftFileTextArea, ui.rightFileTextArea, ui.leftLinenumbers, ui.rightLinenumbers)
    for w in widgets:
        w.config(state=NORMAL)
        w.delete(1.0, END)

    left, right = ui.leftFileTextArea, ui.rightFileTextArea
    leftlineno = rightlineno = 1
    widest = 1
    for line in diff:
        code = line['code']
        if code == DiffCode.SIMILAR:
            left.insert('end', line['line'] + '\n')
            right.insert('end', line['line'] + '\n')
        elif code == DiffCode.RIGHTONLY:
            left.insert('end', '\n', 'gray')
            right.insert('end', line['line'] + '\n', 'green')
        elif code == DiffCode.LEFTONLY:
            left.insert('end', line['line'] + '\n', 'red')
            right.insert('end', '\n', 'gray')
        elif code == DiffCode.CHANGED:
            for (i, c) in enumerate(line['line']):
                left.insert('end', c, 'darkred' if i in line['leftchanges'] else 'red')
            for (i, c) in enumerate(line['newline']):
                right.insert('end', c, 'darkgreen' if i in line['rightchanges'] else 'green')
            left.insert('end', '\n')
            right.insert('end', '\n')

        if code == DiffCode.LEFTONLY:
            l, r = label(left_linenos, leftlineno), ''
            leftlineno += 1
        elif code == DiffCode.RIGHTONLY:
            l, r = '', label(right_linenos, rightlineno)
            rightlineno += 1
        else:
            l, r = label(left_linenos, leftlineno), label(right_linenos, rightlineno)
            leftlineno += 1
            rightlineno += 1
        ui.leftLinenumbers.insert('end', l + '\n', 'line')
        ui.rightLinenumbers.insert('end', r + '\n', 'line')
        widest = max(widest, len(l), len(r))

    ui.leftLinenumbers.config(width=widest + 1)
    ui.rightLinenumbers.config(width=widest + 1)

    for w in widgets:
        w.config(state=DISABLED)
