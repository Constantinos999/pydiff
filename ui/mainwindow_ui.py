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
"""

try:    # for Python2
    from Tkinter import *
    from tkMessageBox import showerror
    from tkFont import Font
    import ttk
    from ttk import Treeview
except ImportError:    # for Python3
    from tkinter import *
    from tkinter.messagebox import showerror
    from tkinter import font
    from tkinter import ttk
    from tkinter.ttk import Treeview
import os
from ui.searchtextdialog import *

class MainWindowUI:

# |   1   |   2   |   3   |   4   |   5   |   6   |   7   |   8   |   9   |  10   |  11   |  12   |
# +-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+
# |                                     menu bar                                                  |
# +-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+
# |  toolbar: previous / next change, view options, export ...                   status text      |
# +-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+
# |               |                                     search bar                                |
# |               |          search entry                                                 | button|
# |               +-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+
# |               |                                       |                                       |
# |               |                                       |                                       |
# |               |                                       |                                       |
# |   treeview    |                                       |                                       |
# |               |              text area 1              |               text area 2             |
# |               |                                       |                                       |
# |               |                                       |                                       |
# |               |                                       |                                       |
# |               |                                       |                                       |
# +-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+-------+
# |   1   |   2   |   3   |   4   |   5   |   6   |   7   |   8   |   9   |  10   |  11   |  12   |

    # Rows
    toolbarRow = 0
    fileTreeRow = filePathLabelsRow = 1
    searchTextRow = 2
    uniScrollbarRow = lineNumbersRow = textAreasRow = 3
    horizontalScrollbarRow = 4

    # Columns
    fileTreeCol = 0
    fileTreeScrollbarCol = 1
    leftLineNumbersCol = leftFilePathLabelsCol = 2    # should span at least two columns
    leftTextAreaCol = leftHorizontalScrollbarCol = 3
    uniScrollbarCol = 4
    rightLineNumbersCol = rightFilePathLabelsCol = 5  # should span at least two columns
    rightTextAreaCol = rightHorizontalScrollbarCol = 6

    # Colors
    whiteColor = '#ffffff'
    redColor = '#ffdcdc'        # removed / changed line (left)
    darkredColor = '#f28b8b'    # the exact characters that changed (left)
    grayColor = '#dddddd'
    lightGrayColor = '#eeeeee'
    greenColor = '#d9f7df'      # added / changed line (right)
    darkgreenColor = '#7fd893'  # the exact characters that changed (right)
    yellowColor = '#f0f58c'
    darkYellowColor = '#ffd700'
    selectColor = '#1e5fd6'         # drag-selected text: strong blue ...
    selectTextColor = '#ffffff'     # ... with white text, readable on any diff colour
    inactiveSelectColor = '#6f97e0' # selection when the window is not focused
    purpleLight = '#F5EBFC'
    blueColor = '#d6ecff'           # folder view: only line endings differ
    foldColor = '#eef1f6'           # 'N unchanged lines hidden' bars
    currentColor = '#9ec2f5'        # line numbers of the change you jumped to

    def __init__(self, window):
        self.main_window = window
        self.main_window.grid_rowconfigure(self.toolbarRow, weight=0)
        self.main_window.grid_rowconfigure(self.filePathLabelsRow, weight=0)
        self.main_window.grid_rowconfigure(self.searchTextRow, weight=0)
        self.main_window.grid_rowconfigure(self.textAreasRow, weight=1)

        self.main_window.grid_columnconfigure(self.fileTreeCol, weight=0)
        self.main_window.grid_columnconfigure(self.fileTreeScrollbarCol, weight=0)
        self.main_window.grid_columnconfigure(self.leftLineNumbersCol, weight=0)
        self.main_window.grid_columnconfigure(self.leftTextAreaCol, weight=1)
        self.main_window.grid_columnconfigure(self.uniScrollbarCol, weight=0)
        self.main_window.grid_columnconfigure(self.rightLineNumbersCol, weight=0)
        self.main_window.grid_columnconfigure(self.rightTextAreaCol, weight=1)
        self.menubar = Menu(self.main_window)
        self.menus = {}
        self.text_area_font = 'TkFixedFont'
        try:
            import tkinter.font as tkfont
        except ImportError:
            import tkFont as tkfont
        self.bold_font = tkfont.nametofont('TkFixedFont').copy()
        self.bold_font.configure(weight='bold')

    # Center window and set its size
    def center_window(self):
        sw = self.main_window.winfo_screenwidth()
        sh = self.main_window.winfo_screenheight()

        w = 0.7 * sw
        h = 0.7 * sh

        x = (sw - w)/2
        y = (sh - h)/2
        self.main_window.geometry('%dx%d+%d+%d' % (w, h, x, y))
        self.main_window.minsize(int(0.3 * sw), int(0.3 * sh))

    def maximise_window(self):
        try:
            self.main_window.state('zoomed')            # Windows, macOS
        except Exception:
            try:
                self.main_window.attributes('-zoomed', True)   # Linux
            except Exception:
                pass

    # Toolbar (filled in by DiffView)
    def create_toolbar(self):
        self.toolbar = ttk.Frame(self.main_window, padding=(4, 3))
        self.toolbar.grid(row=self.toolbarRow, column=0, columnspan=7, sticky=EW)
        return self.toolbar

    # Menu bar
    def add_menu(self, menuName, commandList):
        self.menus[menuName] = menu = Menu(self.menubar,tearoff=0)
        for c in commandList:
            if 'separator' in c:
                menu.add_separator()
                continue
            opts = dict(label=c['name'], accelerator=c.get('accelerator', ''))
            if 'command' in c:
                opts['command'] = c['command']
            if 'variable' in c and 'value' in c:     # one of a set of choices
                menu.add_radiobutton(variable=c['variable'], value=c['value'], **opts)
            elif 'variable' in c:                    # on/off option
                menu.add_checkbutton(variable=c['variable'], **opts)
            else:
                menu.add_command(**opts)
        self.menubar.add_cascade(label=menuName, menu=self.menus[menuName])
        self.main_window.config(menu=self.menubar)

    # Labels
    def create_file_path_labels(self):
        self.leftFileLabel = Label(self.main_window, anchor='center', width=1000, background=self.lightGrayColor)
        self.leftFileLabel.grid(row=self.filePathLabelsRow, column=self.leftFilePathLabelsCol, columnspan=2)
        self.rightFileLabel = Label(self.main_window, anchor='center', width=1000, background=self.lightGrayColor)
        self.rightFileLabel.grid(row=self.filePathLabelsRow, column=self.rightFilePathLabelsCol, columnspan=2)

    # Search text entry
    def create_search_text_entry(self, searchButtonCallback):
        self.searchTextDialog = SearchTextDialog(self.main_window, [self.leftFileTextArea, self.rightFileTextArea], searchButtonCallback)
        self.searchTextDialog.grid(row=self.searchTextRow, column=self.leftFilePathLabelsCol, columnspan=5, sticky=EW)

        self.searchTextDialog.grid_remove()

    # File treeview
    def create_file_treeview(self):
        self.fileTreeView = Treeview(self.main_window)
        self.fileTreeYScrollbar = Scrollbar(self.main_window, orient='vertical', command=self.fileTreeView.yview)
        self.fileTreeXScrollbar = Scrollbar(self.main_window, orient='horizontal', command=self.fileTreeView.xview)
        self.fileTreeView.configure(yscroll=self.fileTreeYScrollbar.set, xscroll=self.fileTreeXScrollbar.set)

        self.fileTreeView.grid(row=self.fileTreeRow, column=self.fileTreeCol, sticky=NS, rowspan=3)
        self.fileTreeYScrollbar.grid(row=self.fileTreeRow, column=self.fileTreeScrollbarCol, sticky=NS, rowspan=3)
        self.fileTreeXScrollbar.grid(row=self.horizontalScrollbarRow, column=self.fileTreeCol, sticky=EW)

        self.fileTreeView.tag_configure('red', background=self.redColor)
        self.fileTreeView.tag_configure('green', background=self.greenColor)
        self.fileTreeView.tag_configure('yellow', background=self.yellowColor)
        self.fileTreeView.tag_configure('purpleLight', background=self.purpleLight)
        self.fileTreeView.tag_configure('blue', background=self.blueColor)

        # hide it until needed
        self.fileTreeView.grid_remove()
        self.fileTreeYScrollbar.grid_remove()
        self.fileTreeXScrollbar.grid_remove()

    # Text areas
    def create_text_areas(self):
        self.leftFileTextArea = Text(self.main_window, padx=5, pady=5, width=1, height=1, bg=self.grayColor)
        self.leftFileTextArea.grid(row=self.textAreasRow, column=self.leftTextAreaCol, sticky=NSEW)
        self.leftFileTextArea.config(font=self.text_area_font)
        self.leftFileTextArea.config(wrap='none')

        self.rightFileTextArea = Text(self.main_window, padx=5, pady=5, width=1, height=1, bg=self.grayColor)
        self.rightFileTextArea.grid(row=self.textAreasRow, column=self.rightTextAreaCol, sticky=NSEW)
        self.rightFileTextArea.config(font=self.text_area_font)
        self.rightFileTextArea.config(wrap='none')

        # highlight tags - every tag on both panes (the in-line view shows
        # removed and added lines in one pane)
        for area in (self.leftFileTextArea, self.rightFileTextArea):
            area.tag_configure('red', background=self.redColor)
            area.tag_configure('darkred', background=self.darkredColor)
            area.tag_configure('green', background=self.greenColor)
            area.tag_configure('darkgreen', background=self.darkgreenColor)
            area.tag_configure('gray', background=self.grayColor)
            area.tag_configure('fold', background=self.foldColor, foreground='#5a6578', justify='center')
            area.tag_configure('message', foreground='#5a6578', justify='center', spacing1=30)
            area.tag_configure('search', background=self.darkYellowColor)

        for area in (self.leftFileTextArea, self.rightFileTextArea):
            # changed characters stand out in bold as well as colour
            area.tag_configure('darkred', font=self.bold_font)
            area.tag_configure('darkgreen', font=self.bold_font)
            # selection: always drawn ON TOP of the diff colours (otherwise the
            # green/red backgrounds hide it), blue with white text
            area.config(selectbackground=self.selectColor, selectforeground=self.selectTextColor,
                        inactiveselectbackground=self.inactiveSelectColor, exportselection=False)
            area.tag_configure('sel', background=self.selectColor, foreground=self.selectTextColor)
            area.tag_raise('search')
            area.tag_raise('sel')
            # Tk on Windows won't let you select in a read-only text unless it has focus
            area.bind('<Button-1>', lambda e: e.widget.focus_set(), add='+')

        # disable the text areas
        self.leftFileTextArea.config(state=DISABLED)
        self.rightFileTextArea.config(state=DISABLED)

    # Line numbers
    def create_line_numbers(self):
        self.leftLinenumbers = Text(self.main_window, width=3, padx=5, pady=5, height=1, bg=self.lightGrayColor)
        self.leftLinenumbers.grid(row=self.lineNumbersRow, column=self.leftLineNumbersCol, sticky=NS)
        self.leftLinenumbers.config(font=self.text_area_font)
        self.leftLinenumbers.tag_configure('line', justify='right')

        self.rightLinenumbers = Text(self.main_window, width=3, padx=5, pady=5, height=1, bg=self.lightGrayColor)
        self.rightLinenumbers.grid(row=self.lineNumbersRow, column=self.rightLineNumbersCol, sticky=NS)
        self.rightLinenumbers.config(font=self.text_area_font)
        self.rightLinenumbers.tag_configure('line', justify='right')
        for nums in (self.leftLinenumbers, self.rightLinenumbers):
            nums.tag_configure('current', background=self.currentColor)
            nums.tag_configure('fold', background=self.foldColor)
            nums.tag_configure('red', background=self.redColor)
            nums.tag_configure('green', background=self.greenColor)
            nums.tag_raise('current')

        # disable the line numbers
        self.leftLinenumbers.config(state=DISABLED)
        self.rightLinenumbers.config(state=DISABLED)

    # Scroll bars
    def scrollBothY(self, *args):
        for w in (self.leftFileTextArea, self.rightFileTextArea, self.leftLinenumbers, self.rightLinenumbers):
            w.yview(*args)

    def updateScrollY(self, first, last, type=None):
        self.leftFileTextArea.yview_moveto(first)
        self.rightFileTextArea.yview_moveto(first)
        self.leftLinenumbers.yview_moveto(first)
        self.rightLinenumbers.yview_moveto(first)
        self.uniScrollbar.set(first, last)

    def scrollBothX(self, *args):
        self.leftFileTextArea.xview(*args)
        self.rightFileTextArea.xview(*args)

    def updateScrollX(self, first, last, type=None):
        self.leftFileTextArea.xview_moveto(first)
        self.rightFileTextArea.xview_moveto(first)
        self.leftHorizontalScrollbar.set(first, last)
        self.rightHorizontalScrollbar.set(first, last)

    def create_scroll_bars(self):
        self.uniScrollbar = Scrollbar(self.main_window)
        self.uniScrollbar.grid(row=self.uniScrollbarRow, column=self.uniScrollbarCol, sticky=NS)
        self.uniScrollbar.config(command=self.scrollBothY)
        self.leftFileTextArea.config(yscrollcommand=self.updateScrollY)
        self.rightFileTextArea.config(yscrollcommand=self.updateScrollY)
        self.leftLinenumbers.config(yscrollcommand=self.updateScrollY)
        self.rightLinenumbers.config(yscrollcommand=self.updateScrollY)

        self.leftHorizontalScrollbar = Scrollbar(self.main_window, orient=HORIZONTAL)
        self.leftHorizontalScrollbar.grid(row=self.horizontalScrollbarRow, column=self.leftHorizontalScrollbarCol, sticky=EW)
        self.leftHorizontalScrollbar.config(command=self.scrollBothX)
        self.leftFileTextArea.config(xscrollcommand=self.updateScrollX)

        self.rightHorizontalScrollbar = Scrollbar(self.main_window, orient=HORIZONTAL)
        self.rightHorizontalScrollbar.grid(row=self.horizontalScrollbarRow, column=self.rightHorizontalScrollbarCol, sticky=EW)
        self.rightHorizontalScrollbar.config(command=self.scrollBothX)
        self.rightFileTextArea.config(xscrollcommand=self.updateScrollX)
