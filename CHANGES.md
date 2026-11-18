# Changes from the original pydiff

This document lists everything changed compared with the original [pydiff](https://github.com/yelsayd/pydiff) by Yasser Elsayed, and why. Changes made November 2026 by Constantinos.

Every bug listed under "Bug fixes" was reproduced with the original code before it was fixed, and each fix was tested afterwards.

---

## Summary

- **8 bug fixes**: wrong or garbled text, scrolling, search, folder comparison and more.
- **New: function-by-function comparison** for Python files.
- **New: one-click Windows launcher** (`Run_PyDiff.bat`) with automatic dependency checks.
- **Clearer highlighting**: readable text selection, bolder changed characters.
- **Better error handling**: problems are reported instead of failing silently.
- **Requires Python 3.8+**. The original targeted Python 2.7, which reached end of life in 2020.

---

## Bug fixes

### 1. Text from UTF-8 files was garbled or blank (Windows)
- **Problem:** Characters such as `é`, `ü` or `–` appeared garbled (`hÃ©llo` instead of `héllo`). Some files showed as completely blank with no error message.
- **Cause:** Files were opened with Python's default encoding. On Windows that's the old `cp1252` code page, not UTF-8, which is what most source code uses. Decoding errors were then silently swallowed by a bare `except:`, leaving the pane empty.
- **Fix:** Files are now read as UTF-8 (with or without a BOM), falling back to cp1252 and then Latin-1, so a file always opens. Any read error is now shown in a message box.
- **Files:** `ui/mainwindow.py` (new `read_text_file()`), `utilities/fileio.py`

### 2. Scrollbar arrows jumped to the top or bottom
- **Problem:** Clicking a scrollbar arrow, or the empty track, jumped to the end of the file instead of moving one line or one page.
- **Cause:** The scrollbar handler treated every scrollbar command as an absolute "move to" position. It ignored the `scroll 1 units` / `scroll 1 pages` forms, so `1` was read as "100%".
- **Fix:** All scrollbar commands are now passed through unchanged to both panes and both line-number columns, so they stay in sync whichever way you scroll.
- **Files:** `ui/mainwindow_ui.py` (`scrollBothY`, `scrollBothX`)

### 3. Find skipped matches
- **Problem:** Find Next could skip matches. In testing it jumped from line 4 straight to line 53, missing a match on line 4.
- **Cause:** The next search position was calculated with `float(index) + 1`. Tk text positions look like `line.column`, so `4.36` became `5.36`: a whole line later, not one character later. Positions such as `3.10` were also misread as `3.1`.
- **Fix:** The search now continues from "the current match + 1 character", using Tk's own index arithmetic.
- **Files:** `ui/searchtextdialog.py`

### 4. Changed files shown as identical in folder comparison
- **Problem:** Two files with different contents could be shown in white ("identical").
- **Cause:** `filecmp.cmp()` was used in its default *shallow* mode, which only compares file size and modification time.
- **Fix:** Files are now compared byte by byte (`shallow=False`).
- **Files:** `ui/mainwindow.py`

### 5. Folders lost their "contains differences" highlight
- **Problem:** A folder containing changed files could be shown as unchanged.
- **Cause:** When processing sub-folders, the "found a difference" flag was *overwritten* by each sub-folder's result rather than combined with it. A sub-folder with no differences cleared a difference found earlier.
- **Fix:** The flag is now only ever set, never cleared.
- **Files:** `ui/mainwindow.py`

### 6. Folder paths broke on Windows
- **Problem:** Folder paths given on the command line with backslashes (e.g. `C:\work\`) weren't cleaned up properly. The folder labels stayed empty when folders were given on the command line.
- **Cause:** Paths were built with `'/'` string joins and trimmed with `rstrip('/')`, which only handles forward slashes.
- **Fix:** Paths use `os.path.join` / `os.path.normpath`, and the folder labels are always filled in. Folder listings are also now sorted (folders first, then alphabetically); before, they came out in random order.
- **Files:** `ui/mainwindow.py`

### 7. Go To Line didn't go to the line
- **Problem:** Ctrl+G only scrolled the left pane, and often not to the requested line.
- **Fix:** Both panes and both line-number columns now scroll together to the requested line.
- **Files:** `ui/mainwindow.py`

### 8. Smaller fixes
- The Paste menu item showed the shortcut **Ctrl+P** instead of **Ctrl+V**.
- Cancelling the second file in *Compare Files* left the window half-loaded; it now cancels cleanly.
- `utilities/fileio.py` called `showerror` without importing it, so it would crash if a file failed to load.
- Selecting a file in the folder tree could misread paths that look like numbers (Tk converts them to integers); paths are now always treated as text.
- An unused `path_to_my_project` variable was removed.

---

## New features

### Function-by-function comparison (Python files)
**File → Compare Functions (Python)**, **Ctrl+K**, or `python pydiff.py -f left.py right.py`.

Both files are parsed with Python's own parser (the standard `ast` module). Every function, class and method is then matched by name, so moved or reordered functions are still paired correctly. Each is given a status:

| Status | How it's decided |
|---|---|
| same | identical text |
| comments/spacing | text differs, but the code is the same once comments, blank lines and spacing are removed (compared token by token with the `tokenize` module) |
| changed | the code differs |
| renamed | in one file only, but its code matches a function that is in the other file only, apart from the name |
| left only / right only | exists in one file only |

Clicking an entry shows the diff of just that function, with real line numbers. Code outside any function (imports, constants) is grouped as *(module-level code)*. A class entry covers the class's own lines (header, class attributes), while its methods are listed separately. *View → Show only differences* hides unchanged entries.

- **New files:** `ui/functioncompare.py` (parsing, matching and the window), `ui/diffview.py`
- **Why `ui/diffview.py`:** the side-by-side drawing code was moved out of `MainWindow` into a shared `render_diff()` function, so the main window and the function window use the same code. It also accepts real line numbers, so a single function shows its true position in each file.

### One-click Windows launcher: `Run_PyDiff.bat`
- Finds a working Python **3.8 or newer**. Any later version is accepted, including a future 4.x, and the newest installed is preferred. It skips the Microsoft Store placeholder `python.exe`, which isn't a real Python.
- If no Python is found, offers to install it with `winget`, or opens the python.org download page.
- Runs the dependency check, then starts pydiff with `pythonw`/`pyw`, so no command window stays open.
- Passes on any files dropped onto it, so you can drag two files or folders onto the launcher to compare them.

### Automatic dependency checking (`pydiff.py`)
On every start (and with `--check-deps`), pydiff checks:
- the Python version (3.8+ is required, for `ast` end-line information);
- that Tkinter is available. It can't be installed with pip, so clear instructions are shown instead;
- that the `difflibparser` submodule is present. If not, it runs `git submodule update --init` itself;
- any third-party packages listed in `PIP_PACKAGES`, installing missing ones with pip (using `ensurepip` first if pip itself is missing). The list is empty at present because pydiff needs none; it's there so any future dependency is handled automatically.

Checks are quick, and anything already installed is left alone.

---

## Display and usability

- **Text selection is readable.** The red and green diff backgrounds used to be drawn *over* the selection, which made selected text a hard-to-read grey on green. The selection is now drawn on top in a strong blue with white text.
- **Changed characters stand out.** The characters that changed within a line are now **bold** as well as darker red or green. The line backgrounds are slightly lighter to increase the contrast.
- **Sharp text on high-DPI Windows screens.** pydiff now tells Windows it handles display scaling, so text is no longer blurry on scaled displays.
- **Clicking into a pane** now gives it keyboard focus, so selecting and copying with Ctrl+C works reliably on Windows.

## Error handling

- Errors are shown in a pop-up rather than lost. This matters because the launcher runs pydiff without a console.
- Crash details are appended to `pydiff_error.log` in the pydiff folder (ignored by git via the existing `*.log` rule).
- Files that can't be read now show a message instead of a blank pane.
- Paths given on the command line are checked, with a clear message if they don't exist.
- Giving one path instead of two now gives a clear error.

## Command line

- Paths can now be given directly (`pydiff.py a.py b.py`) as well as with the original `-p a.py b.py`.
- New options: `-f` / `--functions` and `--check-deps`.
- pydiff can be started from any folder. It no longer has to be run from inside its own folder.

---

## Compatibility notes

- **Python 3.8 or newer is required.** The original README targeted Python 2.7, which has been unsupported since 2020. The Python 2 import fallbacks in the UI files were left in place but are no longer used.
- `difflibparser` (the submodule) is **unchanged** and still points to the original repository.
- Everything that worked before still works the same way. The new features are additions.

## Files changed

| File | Status | Summary |
|---|---|---|
| `pydiff.py` | modified | dependency checks, argument handling, error reporting, DPI fix |
| `ui/mainwindow.py` | modified | bug fixes 1, 4-8; Compare Functions menu; uses shared `render_diff` |
| `ui/mainwindow_ui.py` | modified | scrolling fix, colours, selection, bold changed characters |
| `ui/searchtextdialog.py` | modified | search position fix |
| `utilities/fileio.py` | modified | missing import, UTF-8 reading |
| `ui/diffview.py` | **new** | shared side-by-side diff drawing |
| `ui/functioncompare.py` | **new** | function-by-function comparison |
| `Run_PyDiff.bat` | **new** | Windows one-click launcher |
| `CHANGES.md` | **new** | this file |
| `screenshot_main.png`, `screenshot_functions.png` | **new** | screenshots for the README |
| `README.md` | rewritten | clearer setup and usage instructions |
| `LICENSE` | modified | added a copyright line for the modifications; original notice kept |

## Licence

The original project is MIT-licensed. Its copyright notice (`Copyright (c) 2016 Yasser Elsayed`) is kept unchanged in `LICENSE` and in every original file, as the licence requires. A second line, `Copyright (c) 2026 Constantinos`, was added beneath it to cover these modifications. The modified version is released under the same MIT License.
