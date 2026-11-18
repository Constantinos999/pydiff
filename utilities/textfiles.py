"""
Copyright (c) 2026 Constantinos
Part of pydiff - MIT License (see the LICENSE file).

Reading text files whatever their encoding, and recognising files that
aren't text at all (images, Word documents, PDFs ...).
"""

import codecs


class BinaryFileError(Exception):
    """The file isn't text, so its contents can't be shown as lines."""


class TextFile(object):
    def __init__(self, text, encoding, newline):
        self.text = text            # contents, with any line ending
        self.encoding = encoding    # e.g. 'UTF-8', 'UTF-16', 'Windows-1252'
        self.newline = newline      # 'CRLF', 'LF', 'CR', 'mixed' or None


def _looks_like_utf16(data):
    """UTF-16 without a byte-order mark: lots of zero bytes on one side."""
    sample = data[:4000]
    if len(sample) < 4:
        return None
    even = sample[0::2].count(0)
    odd = sample[1::2].count(0)
    half = len(sample) // 2
    if odd > half * 0.4 and even < half * 0.05:
        return 'utf-16-le'
    if even > half * 0.4 and odd < half * 0.05:
        return 'utf-16-be'
    return None


def _newline_style(text):
    crlf = text.count('\r\n')
    lf = text.count('\n') - crlf
    cr = text.count('\r') - crlf
    kinds = [name for name, n in (('CRLF', crlf), ('LF', lf), ('CR', cr)) if n]
    if not kinds:
        return None
    return kinds[0] if len(kinds) == 1 else 'mixed'


def decode(data):
    """Bytes -> TextFile. Raises BinaryFileError for non-text data."""
    if data.startswith(codecs.BOM_UTF8):
        text, enc = data[len(codecs.BOM_UTF8):].decode('utf-8', 'replace'), 'UTF-8 (BOM)'
    elif data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE):
        text, enc = data.decode('utf-16', 'replace'), 'UTF-16'
    else:
        guess = _looks_like_utf16(data)
        if guess:
            text, enc = data.decode(guess, 'replace'), 'UTF-16'
        elif b'\x00' in data[:8000]:
            raise BinaryFileError('This is not a text file (it contains binary data), '
                                  'so its contents cannot be shown.')
        else:
            try:
                text, enc = data.decode('utf-8'), 'UTF-8'
            except UnicodeDecodeError:
                try:
                    text, enc = data.decode('cp1252'), 'Windows-1252'
                except UnicodeDecodeError:
                    text, enc = data.decode('latin-1'), 'Latin-1'
    return TextFile(text, enc, _newline_style(text))


def read_file(path):
    with open(path, 'rb') as f:
        return decode(f.read())


def read_text_file(path):
    """Just the text of a file (any encoding)."""
    return read_file(path).text


def split_lines(text):
    """Split on real line endings only (\\r\\n, \\n, \\r). str.splitlines() also
    splits on form feeds and other rare characters, which threw the line
    numbers out compared with a text editor."""
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return lines


def same_ignoring_line_endings(path_a, path_b):
    """True if two files have the same text once line endings (and encoding)
    are ignored."""
    try:
        a, b = read_file(path_a), read_file(path_b)
    except (OSError, BinaryFileError):
        return False
    return split_lines(a.text) == split_lines(b.text)
