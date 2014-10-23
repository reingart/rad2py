#!/usr/bin/env python
# coding:utf-8

"PSP Program 2A - Count Program LOC"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"


from tokenize import generate_tokens, NEWLINE, COMMENT, NL
import token

# WARNING: it seems that tokenize counts BOM as a logical line!

def count_logical_lines(filename):
    """Count logical python lines and comments using Tokenizer
    
    >>> f = open("test1.py", "w")
    >>> f.write('#test\n\"\"\"docstring\n\"\"\"\n(1+\n1)\n\n')
    >>> f.close()
    >>> count, comments = count_logical_lines("test1.py")
    >>> count
    2
    >>> comments
    1
    """
    locs = 0
    comments = 0
    with open(filename) as f:
        g = generate_tokens(f.readline)   # tokenize
        for toknum, tokval, start, end, line in g:
            if toknum == NEWLINE:  # count logical line:
                locs += 1
            if toknum == COMMENT:
                comments += 1
    return locs, comments


def logical_to_physical_count(filename):
    """Place every logical line into a pythical line and count physical lines

    >>> f = open("test1.py", "w")
    >>> f.write('#test\n\"\"\"docstring\n\"\"\"\n(1+\n1)\n\n')
    >>> f.close()
    >>> logical_to_physical_count("test1.py")
    2
    """

    # convert physical to logical lines:
    with open(filename) as f:
        with open(filename + ".phy", "w") as out:
            g = generate_tokens(f.readline)   # tokenize
            prev_toknum = None
            last_col = 0
            buf = ""
            ident = 0
            for toknum, tokval, start, end, line in g:
                srow, scol = start
                erow, ecol = end
                if toknum == token.INDENT:      # increment identation
                    ident += 1
                elif toknum == token.DEDENT:    # decrement identation
                    ident -= 1
                elif toknum == token.STRING and prev_toknum in (token.INDENT,
                    token.NEWLINE, NL, None):
                    # Docstring detected, replace by a single line
                    buf += "'docstring - 1 SLOC'"
                elif toknum == COMMENT:
                    # comment, do nothing
                    pass
                elif toknum == NEWLINE:
                    if buf:
                        out.write("%s%s\n" % ("    " * ident, buf))
                        buf = ""
                        last_col = 0
                elif toknum == NL:
                    # ignore internal new lines (add space to preserve syntax)
                    if buf:
                        buf += " "
                elif tokval:
                    # logical line (docstrig previously printed):
                    if last_col < scol:
                        buf += " "
                    buf += "%s" % tokval
                prev_toknum = toknum
                last_col = ecol

    # count new physical lines from output file:
    count = 0
    with open(filename + ".phy")  as f:
        for line in f:
            # fail if it is a comment
            assert not line.strip().startswith("#")
            # fail if it is blank
            assert len(line.strip()) > 0
            count += 1

    return count


if __name__ == "__main__":
    # test program1A
    loc1, comments1 = count_logical_lines("program1A.py")
    phy_loc1 = logical_to_physical_count("program1A.py")
    print loc1, phy_loc1, comments1
    assert loc1 == 21
    assert comments1 == 5
    assert phy_loc1 == loc1
    # test program2A
    loc2, comments2 = count_logical_lines("program2A.py")
    phy_loc2 = logical_to_physical_count("program2A.py")
    print loc2, phy_loc2, comments2
    assert loc2 == 73
    assert comments2 == 18
    assert phy_loc2 == loc2
