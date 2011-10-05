#!/usr/bin/env python
# coding:utf-8

"File facilities enhancing python stdlib or builtins (unicode, line-endings)"

# Byte-Order-Mark detection inspired by DrPython

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"


import codecs
import locale
import re
import wx.stc
 
PY_CODING_RE = re.compile(r'coding[:=]\s*([-\w.]+)')


def unicode_file_read(f, encoding):
    "Detect python encoding or BOM, returns unicode text, encoding, bom, eol"
    bom = None
    start = 0
    # detect encoding
    sniff = f.read(240)
    match = PY_CODING_RE.search(sniff)
    if match:
        encoding = match.group(1)
    # First 2 to 4 bytes are BOM?
    boms = (codecs.BOM, codecs.BOM_BE, codecs.BOM_LE, codecs.BOM_UTF8, 
            codecs.BOM_UTF16, codecs.BOM_UTF16_BE, codecs.BOM_UTF16_LE,
            codecs.BOM_UTF32, codecs.BOM_UTF32_BE, codecs.BOM_UTF32_LE)
    encodings = ("utf_16", "utf_16_be", "utf_16_le", "utf_8", 
                 "utf_16", "utf_16_be", "utf_16_le", None, None, None)                    
    for i, bom in enumerate(boms):
        if sniff[:len(bom)] == bom:
            if encoding is None:
                encoding = encodings[i]
            start = len(bom)
            bom = bom
            break
    else:
        # no BOM found, use to platform default if no encoding specified
        if not encoding:
            encoding = locale.getpreferredencoding()
        bom = None

    if not encoding:
        raise RuntimeError("Unsupported encoding!")

    # detect line endings ['CRLF', 'CR', 'LF'][self.eol]
    # (not always there is a file.newlines -using universal nl support-)
    f.seek(start)
    line = f.readline()
    if line[-2:-1] in ['\n', '\r']:
        newlines = line[-2:]
    else:
        newlines = line[-1:]
    if newlines:
        eol = {'\r\n': wx.stc.STC_EOL_CRLF, '\n\r': wx.stc.STC_EOL_CRLF,
               '\r': wx.stc.STC_EOL_CR, 
               '\n': wx.stc.STC_EOL_LF}[newlines]
    else:
        eol = wx.stc.STC_EOL_CRLF
        newlines = '\r\n'
    # rewind and read text (in the proper encoding)
    f.seek(start)
    return f.read().decode(encoding), encoding, bom, eol, newlines

