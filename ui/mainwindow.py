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

import os, filecmp
from ui.mainwindow_ui import MainWindowUI
from ui.diffview import DiffView
from ui.functioncompare import open_function_compare
from utilities.textfiles import read_file, read_text_file, BinaryFileError, same_ignoring_line_endings
from utilities.settings import Settings
from utilities import gittools
try:    # for Python2
    from Tkinter import *
    from tkFileDialog import askopenfilename, askdirectory
    from tkSimpleDialog import askstring, askinteger
    from tkMessageBox import showerror, showinfo, askyesno
except ImportError:    # for Python3
    from tkinter import *
    from tkinter.filedialog import askopenfilename, askdirectory
    from tkinter.simpledialog import askstring, askinteger
    from tkinter.messagebox import showerror, showinfo, askyesno

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class MainWindow:
    def start(self, leftpath = None, rightpath = None, functions = False):
        self.settings = Settings()
        self.main_window = Tk()
        self.main_window.title('Pydiff')
        self.__main_window_ui = ui = MainWindowUI(self.main_window)

        self.leftFile = ''
        self.rightFile = ''
        self.leftDir = self.rightDir = None
        self.functionWindow = None

        ui.center_window()
        if self.settings.get('start_maximised'):
            ui.maximise_window()
        ui.create_file_path_labels()
        ui.create_text_areas()
        ui.create_search_text_entry(self.__findNext)
        ui.create_line_numbers()
        ui.create_scroll_bars()
        ui.create_file_treeview()
        self.view = DiffView(ui, self.settings,
                             extra_buttons=[('Compare functions', self.__compare_functions)])

        self.maximised_var = BooleanVar(value=self.settings.get('start_maximised'))
        self.line_endings_var = BooleanVar(value=self.settings.get('ignore_line_endings'))

        ui.add_menu('File', [
            {'name': 'Compare Files…', 'command': self.__browse_files, 'accelerator': 'Ctrl+O'},
            {'name': 'Compare Directories…', 'command': self.__browse_directories},
            {'separator'},
            {'name': 'Compare Functions (Python)', 'command': self.__compare_functions, 'accelerator': 'Ctrl+K'},
            {'separator'},
            {'name': 'Export Results…', 'command': self.view.export, 'accelerator': 'Ctrl+E'},
            {'separator'},
            {'name': 'Exit', 'command': self.__exit, 'accelerator': 'Alt+F4'}
            ])
        ui.add_menu('Edit', [
            {'name': 'Find', 'command': self.__startFindText, 'accelerator': 'Ctrl+F'},
            {'name': 'Copy', 'command': self.__copy, 'accelerator': 'Ctrl+C'},
            {'separator'},
            {'name': 'Go To Line', 'command': self.__goToLine, 'accelerator': 'Ctrl+G'}
            ])
        ui.add_menu('View', self.view.view_menu_items() + [
            {'separator'},
            {'name': 'Start Maximised', 'variable': self.maximised_var, 'command': self.__toggle_maximised},
            {'name': 'Folders: Ignore Line-Ending-Only Differences', 'variable': self.line_endings_var,
             'command': self.__toggle_line_endings},
            ])
        ui.add_menu('Git', [
            {'name': 'Compare File With Last Commit…', 'command': lambda: self.__compare_with_commit('HEAD'),
             'accelerator': 'Ctrl+L'},
            {'name': 'Compare File With Commit…', 'command': lambda: self.__compare_with_commit(None)},
            {'separator'},
            {'name': 'Use pydiff as Git\'s Diff Viewer…', 'command': self.__setup_difftool},
            ])
        ui.fileTreeView.bind('<<TreeviewSelect>>', lambda *x:self.treeViewItemSelected())
        # Alt+Up/Down move between changes, not tree items
        ui.fileTreeView.bind('<Alt-Down>', lambda e: (self.view.next_change(), 'break')[1])
        ui.fileTreeView.bind('<Alt-Up>', lambda e: (self.view.previous_change(), 'break')[1])

        if (leftpath and os.path.isdir(leftpath)) or (rightpath and os.path.isdir(rightpath)):
            self.__load_directories(leftpath, rightpath)
        else:
            self.leftFile = leftpath if leftpath else ''
            self.rightFile = rightpath if rightpath else ''
            self.filesChanged()

        self.__bind_key_shortcuts()

        if functions and self.leftFile and self.rightFile:
            self.main_window.after(200, self.__compare_functions)

        self.main_window.mainloop()

    def __bind_key_shortcuts(self):
        w = self.main_window
        w.bind('<Control-f>', lambda *x: self.__startFindText())
        w.bind('<Control-g>', lambda *x: self.__goToLine())
        w.bind('<Control-k>', lambda *x: self.__compare_functions())
        w.bind('<Control-o>', lambda *x: self.__browse_files())
        w.bind('<Control-l>', lambda *x: self.__compare_with_commit('HEAD'))
        w.bind('<Escape>', lambda *x: self.__endFindText())
        w.bind('<F3>', self.__main_window_ui.searchTextDialog.nextResult)

    # ------------------------------------------------------------- options
    def __toggle_maximised(self):
        on = bool(self.maximised_var.get())
        self.settings.set('start_maximised', on)
        if on:
            self.__main_window_ui.maximise_window()

    def __toggle_line_endings(self):
        self.settings.set('ignore_line_endings', bool(self.line_endings_var.get()))
        if self.leftDir and self.rightDir:
            self.__load_directories(self.leftDir, self.rightDir)

    # ------------------------------------------------------------- files
    def __browse_files(self):
        if not self.__load_file('left'):
            return
        if not self.__load_file('right'):
            return
        self.__hide_tree()
        self.filesChanged()

    def __hide_tree(self):
        ui = self.__main_window_ui
        ui.fileTreeView.grid_remove()
        ui.fileTreeYScrollbar.grid_remove()
        ui.fileTreeXScrollbar.grid_remove()
        self.leftDir = self.rightDir = None

    # Load directories into the treeview
    def __browse_directories(self):
        leftDir = self.__load_directory('left')
        if not leftDir:
            return
        rightDir = self.__load_directory('right')
        self.__load_directories(leftDir, rightDir)

    def __load_directories(self, leftDir, rightDir):
        if leftDir and rightDir:
            if not (os.path.isdir(leftDir) and os.path.isdir(rightDir)):
                showerror('Compare Directories', 'Both paths must be folders to compare directories.')
                return
            ui = self.__main_window_ui
            self.leftDir, self.rightDir = leftDir, rightDir
            self.leftFile = self.rightFile = ''
            self.view.clear()
            self.view.set_titles(leftDir, rightDir)
            self.view.status_var.set('Pick a file in the list on the left to compare it')
            self.main_window.title('Pydiff - %s vs %s' % (os.path.basename(os.path.normpath(leftDir)),
                                                         os.path.basename(os.path.normpath(rightDir))))
            ui.fileTreeView.grid()
            ui.fileTreeYScrollbar.grid()
            ui.fileTreeXScrollbar.grid()
            ui.fileTreeView.delete(*ui.fileTreeView.get_children())
            self.__browse_process_directory('', leftDir, rightDir)

    # Recursive method to fill the treeview with given directory hierarchy
    def __browse_process_directory(self, parent, leftPath, rightPath):
        tree = self.__main_window_ui.fileTreeView
        if parent == '':
            leftPath = os.path.normpath(leftPath)
            rightPath = os.path.normpath(rightPath)
            tree.heading('#0', text=os.path.basename(leftPath) + ' / ' + os.path.basename(rightPath), anchor=W)
        try:
            leftListing = os.listdir(leftPath)
            rightListing = os.listdir(rightPath)
        except OSError as e:
            tree.insert(parent, 'end', text='(cannot read folder: %s)' % e.strerror, tags=('red',))
            return True
        # folders first, then files, alphabetically (the original order was random)
        mergedListing = sorted(set(leftListing) | set(rightListing),
            key=lambda n: (not (os.path.isdir(os.path.join(leftPath, n)) or os.path.isdir(os.path.join(rightPath, n))), n.lower()))
        ignore_endings = self.settings.get('ignore_line_endings')
        painted = FALSE
        for l in mergedListing:
            newLeftPath = os.path.join(leftPath, l)
            newRightPath = os.path.join(rightPath, l)
            bindValue = (newLeftPath, newRightPath)
            # Item in left dir only
            if l in leftListing and l not in rightListing:
                tree.insert(parent, 'end', text=l, value=bindValue, open=False, tags=('red','simple'))
                painted = TRUE
            # Item in right dir only
            elif l in rightListing and l not in leftListing:
                tree.insert(parent, 'end', text=l, value=bindValue, open=False, tags=('green','simple'))
                painted = TRUE
            # Item in both dirs
            else:
                # If one of the diffed items is a file and the other is a directory, show in yellow indicating a difference
                if os.path.isdir(newLeftPath) != os.path.isdir(newRightPath):
                    tree.insert(parent, 'end', text=l, value=bindValue, open=False, tags=('yellow','simple'))
                    painted = TRUE
                elif os.path.isdir(newLeftPath):
                    # Both are directories: recurse; colour the folder if anything inside differs
                    oid = tree.insert(parent, 'end', text=l, open=False)
                    if self.__browse_process_directory(oid, newLeftPath, newRightPath):
                        tree.item(oid, tags=('purpleLight', 'simple'))
                        painted = TRUE
                else:
                    # Both are files: identical (white), only line endings differ (blue) or different (yellow)
                    try:
                        same = filecmp.cmp(newLeftPath, newRightPath, shallow=False)
                    except OSError:
                        same = False
                    if same:
                        tree.insert(parent, 'end', text=l, value=bindValue, open=False, tags=('simple',))
                    elif ignore_endings and same_ignoring_line_endings(newLeftPath, newRightPath):
                        tree.insert(parent, 'end', text=l, value=bindValue, open=False, tags=('blue', 'simple'))
                    else:
                        tree.insert(parent, 'end', text=l, value=bindValue, open=False, tags=('yellow','simple'))
                        painted = TRUE
        return painted

    def __load_file(self, pos):
        fname = askopenfilename(title='Compare files - choose the %s file' % pos.upper())
        if fname:
            if pos == 'left':
                self.leftFile = fname
            else:
                self.rightFile = fname
            return fname
        else:
            return None

    def __load_directory(self, pos):
        return askdirectory(title='Compare folders - choose the %s folder' % pos.upper()) or None

    # Callback for changing a file path
    def filesChanged(self, left_title=None, right_title=None):
        view = self.view
        if not self.leftFile or not self.rightFile:
            view.clear()
            return
        view.set_titles(left_title or self.leftFile, right_title or self.rightFile)
        self.main_window.title('Pydiff - %s vs %s' % (os.path.basename(left_title or self.leftFile),
                                                     os.path.basename(right_title or self.rightFile)))

        if os.path.isdir(self.leftFile) or os.path.isdir(self.rightFile):
            view.show_message('One side is a folder and the other is a file,\nso there is nothing to compare line by line.',
                              status='Folder vs file')
            return

        files, errors, binary = [], [], False
        for path in (self.leftFile, self.rightFile):
            try:
                files.append(read_file(path))
            except BinaryFileError:
                binary = True
                files.append(None)
            except Exception as e:
                errors.append('%s\n%s' % (path, e))
                files.append(None)
        if errors:
            showerror('Could not read file', '\n\n'.join(errors))
            view.show_message('This file could not be read.', status='Could not read file')
            return
        if binary:
            try:
                same = filecmp.cmp(self.leftFile, self.rightFile, shallow=False)
            except OSError:
                same = False
            verdict = 'The two files are IDENTICAL.' if same else 'The two files are DIFFERENT.'
            view.show_message('This is not a text file (e.g. an image, PDF or Word document),\n'
                              'so its contents cannot be shown line by line.\n\n' + verdict,
                              status='Binary files: ' + ('identical' if same else 'different'))
            return

        left, right = files
        notes = []
        if left.encoding != right.encoding:
            notes.append('Encoding: %s → %s' % (left.encoding, right.encoding))
        if left.newline and right.newline and left.newline != right.newline:
            notes.append('Line endings: %s → %s' % (left.newline, right.newline))
        view.show(left.text, right.text, notes=notes)

    def treeViewItemSelected(self):
        item_id = self.__main_window_ui.fileTreeView.focus()
        paths = self.__main_window_ui.fileTreeView.item(item_id)['values']
        if paths == None or len(paths) == 0:
            return
        self.leftFile = str(paths[0])
        self.rightFile = str(paths[1])
        self.filesChanged()

    # ------------------------------------------------------------- git
    def __compare_with_commit(self, ref):
        start = self.rightFile if self.rightFile and os.path.isfile(self.rightFile) else ''
        path = askopenfilename(title='Compare with git - choose the file',
                               initialdir=os.path.dirname(start) if start else None,
                               initialfile=os.path.basename(start) if start else None)
        if not path:
            return
        if ref is None:
            ref = askstring('Compare with commit',
                            'Commit, branch or tag to compare with\n'
                            '(e.g. HEAD~1 = the commit before last, main, v1.0, a1b2c3d):',
                            initialvalue='HEAD~1')
            if not ref:
                return
        try:
            old, short = gittools.file_at_commit(path, ref.strip())
        except gittools.GitError as e:
            showerror('Compare with git', str(e))
            return
        self.__hide_tree()
        self.leftFile, self.rightFile = old, os.path.abspath(path)
        name = os.path.basename(path)
        label = 'last commit' if ref == 'HEAD' else ref
        self.filesChanged('%s  @ %s (%s)' % (name, short, label), '%s  (current file)' % path)

    def __setup_difftool(self):
        script = os.path.join(APP_DIR, 'pydiff.py')
        cmd = gittools.pydiff_command(script)
        if not askyesno('Use pydiff with git',
                        'This sets pydiff as git\'s diff viewer for your user account '
                        '(all repositories), by running:\n\n'
                        'git config --global difftool.pydiff.cmd \'%s\'\n'
                        'git config --global difftool.prompt false\n'
                        'git config --global diff.tool pydiff\n\n'
                        'Afterwards, in any repository:\n'
                        '   git difftool            compare changed files one by one\n'
                        '   git difftool -d         compare the whole folder at once\n'
                        '   git difftool HEAD~1     compare with the commit before last\n\n'
                        'Your normal "git diff" is not affected. Go ahead?' % cmd):
            return
        try:
            gittools.setup_difftool(script)
        except gittools.GitError as e:
            showerror('Use pydiff with git', str(e))
            return
        showinfo('Use pydiff with git', 'Done. Run "git difftool" in any repository to compare changes in pydiff.')

    # ------------------------------------------------------------- edit
    def __copy(self):
        area = self.__getActiveTextArea()
        if area:
            area.event_generate("<<Copy>>")

    def __getActiveTextArea(self):
        if self.main_window.focus_get() == self.__main_window_ui.leftFileTextArea:
            return self.__main_window_ui.leftFileTextArea
        elif self.main_window.focus_get() == self.__main_window_ui.rightFileTextArea:
            return self.__main_window_ui.rightFileTextArea
        else:
            return None

    def __goToLine(self):
        line = askstring('Go to line', 'Enter line number (of the left file):')
        if line:
            try:
                linenumber = int(line)
            except ValueError:
                return
            target = self.view.display_line_for(linenumber)
            if target:
                self.view.scroll_to_line(target)

    def __startFindText(self):
        self.__main_window_ui.searchTextDialog.grid()
        self.__main_window_ui.searchTextDialog.focus()

    def __endFindText(self):
        self.__main_window_ui.leftFileTextArea.tag_remove('search', 1.0, END)
        self.__main_window_ui.rightFileTextArea.tag_remove('search', 1.0, END)
        self.__main_window_ui.searchTextDialog.unfocus()
        self.__main_window_ui.searchTextDialog.grid_remove()

    def __findNext(self, searchresult):
        term,leftpos,rightpos = searchresult['term'], searchresult['indices'][0], searchresult['indices'][1]
        if leftpos != -1:
            self.__main_window_ui.leftFileTextArea.tag_remove('search', 1.0, END)
            self.__main_window_ui.leftFileTextArea.tag_add('search', leftpos, '%s + %sc' % (leftpos, len(term)))
            self.__main_window_ui.leftFileTextArea.see(leftpos)
        if rightpos != -1:
            self.__main_window_ui.rightFileTextArea.tag_remove('search', 1.0, END)
            self.__main_window_ui.rightFileTextArea.tag_add('search', rightpos, '%s + %sc' % (rightpos, len(term)))
            self.__main_window_ui.rightFileTextArea.see(rightpos)

    # Function-by-function comparison of the current pair of Python files.
    # If no pair of files is loaded (or a folder is selected), ask for two files.
    def __compare_functions(self):
        left, right = self.leftFile, self.rightFile
        if not (left and right and os.path.isfile(left) and os.path.isfile(right)):
            types = [('Python files', '*.py *.pyw'), ('All files', '*.*')]
            left = askopenfilename(title='Compare functions - choose LEFT file', filetypes=types)
            if not left:
                return
            right = askopenfilename(title='Compare functions - choose RIGHT file', filetypes=types)
            if not right:
                return
            self.__hide_tree()
            self.leftFile, self.rightFile = left, right
            self.filesChanged()
        self.functionWindow = open_function_compare(self.main_window, left, right, read_text_file,
                                                    showerror, self.settings)

    def __exit(self):
        self.main_window.destroy()
