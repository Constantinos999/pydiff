"""
Copyright (c) 2026 Constantinos
Part of pydiff - MIT License (see the LICENSE file).

The comparison engine. Turns two lists of lines into a list of Rows, one per
line of output, which every view (side-by-side, in-line, export) draws from.

Uses difflib.SequenceMatcher on whole lines, then character-level matching
only within changed blocks. This is much faster on large files than
difflib.ndiff (used by the original), which fuzzy-matches every removed line
against every added line in a changed block.
"""

import difflib

SAME, CHANGED, LEFT, RIGHT = 'same', 'changed', 'left', 'right'

# Lines this similar (0..1) are shown as one changed line with the changed
# characters highlighted; less similar lines are shown as removed + added.
PAIR_THRESHOLD = 0.6
# Character-level matching is skipped for very long lines (it gets slow and
# the result isn't readable anyway); they are shown fully highlighted.
MAX_INTRALINE = 2000


class Row(object):
    __slots__ = ('kind', 'left', 'right', 'lno', 'rno', 'lchg', 'rchg')

    def __init__(self, kind, left, right, lno, rno, lchg=None, rchg=None):
        self.kind = kind      # SAME, CHANGED, LEFT (removed) or RIGHT (added)
        self.left = left      # left text, or None
        self.right = right    # right text, or None
        self.lno = lno        # real left line number, or None
        self.rno = rno        # real right line number, or None
        self.lchg = lchg or []  # [(start, end)] changed character ranges, left
        self.rchg = rchg or []  # same for right

    def __repr__(self):
        return 'Row(%s, %r, %r)' % (self.kind, self.left, self.right)


def _char_ranges(a, b):
    """Changed character ranges in a and in b."""
    if len(a) > MAX_INTRALINE or len(b) > MAX_INTRALINE:
        return [(0, len(a))], [(0, len(b))]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    left, right = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if i2 > i1:
            left.append((i1, i2))
        if j2 > j1:
            right.append((j1, j2))
    return left, right


def _similar(a, b):
    if a.strip() == b.strip():
        return True
    if not a.strip() or not b.strip():
        return False
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < PAIR_THRESHOLD or sm.quick_ratio() < PAIR_THRESHOLD:
        return False
    return len(a) + len(b) > 2 * MAX_INTRALINE or sm.ratio() >= PAIR_THRESHOLD


LOOKAHEAD = 8   # how far ahead to look for a matching partner line


def _replace_block(a, b, i1, j1, lnums, rnums, rows):
    """Lay out a block where lines a were replaced by lines b, pairing each
    edited line with its closest-matching partner within a few lines."""
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            rows.append(Row(SAME, a[i], b[j], lnums[i1 + i], rnums[j1 + j]))
            i += 1
            j += 1
            continue
        if _similar(a[i], b[j]):
            lc, rc = _char_ranges(a[i], b[j])
            rows.append(Row(CHANGED, a[i], b[j], lnums[i1 + i], rnums[j1 + j], lc, rc))
            i += 1
            j += 1
            continue
        # nearest partner: skip d added lines, or d removed lines
        found = None
        for d in range(1, LOOKAHEAD + 1):
            if j + d < len(b) and _similar(a[i], b[j + d]):
                found = ('added', d)
                break
            if i + d < len(a) and _similar(a[i + d], b[j]):
                found = ('removed', d)
                break
        if found and found[0] == 'added':
            for k in range(found[1]):
                rows.append(Row(RIGHT, None, b[j + k], None, rnums[j1 + j + k]))
            j += found[1]
        elif found:
            for k in range(found[1]):
                rows.append(Row(LEFT, a[i + k], None, lnums[i1 + i + k], None))
            i += found[1]
        else:
            rows.append(Row(LEFT, a[i], None, lnums[i1 + i], None))
            i += 1
    for k in range(i, len(a)):
        rows.append(Row(LEFT, a[k], None, lnums[i1 + k], None))
    for k in range(j, len(b)):
        rows.append(Row(RIGHT, None, b[k], None, rnums[j1 + k]))


def compare_lines(left_lines, right_lines, left_numbers=None, right_numbers=None):
    """Compare two lists of lines and return a list of Rows.

    left_numbers / right_numbers: the real line number of each line, for
    when only part of a file is being compared. Default 1, 2, 3...
    """
    lnums = left_numbers or list(range(1, len(left_lines) + 1))
    rnums = right_numbers or list(range(1, len(right_lines) + 1))
    # blank lines aren't used as anchors (as in difflib.ndiff), otherwise an
    # inserted blank line can split an edited line from its new version
    sm = difflib.SequenceMatcher(lambda line: not line.strip(), left_lines, right_lines, autojunk=False)
    rows = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                rows.append(Row(SAME, left_lines[i1 + k], right_lines[j1 + k], lnums[i1 + k], rnums[j1 + k]))
        elif tag == 'delete':
            for i in range(i1, i2):
                rows.append(Row(LEFT, left_lines[i], None, lnums[i], None))
        elif tag == 'insert':
            for j in range(j1, j2):
                rows.append(Row(RIGHT, None, right_lines[j], None, rnums[j]))
        else:
            _replace_block(left_lines[i1:i2], right_lines[j1:j2], i1, j1, lnums, rnums, rows)
    return rows


def change_blocks(rows):
    """[(first_row_index, last_row_index)] of each run of differing rows."""
    blocks, start = [], None
    for i, r in enumerate(rows):
        if r.kind != SAME:
            if start is None:
                start = i
        elif start is not None:
            blocks.append((start, i - 1))
            start = None
    if start is not None:
        blocks.append((start, len(rows) - 1))
    return blocks


def visible_rows(rows, context):
    """Rows to display when only changes (plus `context` lines around them)
    are wanted. Hidden stretches become a single int: the number of lines hidden.
    context=None shows everything."""
    if context is None:
        return list(rows)
    keep = [False] * len(rows)
    for (a, b) in change_blocks(rows):
        for i in range(max(0, a - context), min(len(rows), b + context + 1)):
            keep[i] = True
    out, hidden = [], 0
    for r, k in zip(rows, keep):
        if k:
            if hidden:
                out.append(hidden)
                hidden = 0
            out.append(r)
        else:
            hidden += 1
    if hidden:
        out.append(hidden)
    return out


def summary(rows):
    """(blocks, lines removed, lines added, lines changed)."""
    removed = sum(1 for r in rows if r.kind == LEFT)
    added = sum(1 for r in rows if r.kind == RIGHT)
    changed = sum(1 for r in rows if r.kind == CHANGED)
    return len(change_blocks(rows)), removed, added, changed
