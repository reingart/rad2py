#!/usr/bin/env python
# coding:utf-8

"PSP Program 3A - Count LOC/object/method"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"


from tokenize import generate_tokens, NEWLINE, COMMENT, NL
import token

# WARNING: it seems that tokenize counts BOM as a logical line!

def find_classes(filename):
    """parse the filename and return {'function', 'lineno'} """

m = pyclbr.readmodule_ex("program1A", path=["/home/reingart/tesis/rad2py/assignments"])
m.items()
[('stddev', <pyclbr.Function instance at 0x3f2bf80>), ('mean', <pyclbr.Function instance at 0x3f2bfc8>)]
m['stddev']
<pyclbr.Function instance at 0x3f2bf80>
f=m['stddev']
f.file
'/home/reingart/tesis/rad2py/assignments/program1A.py'
f.lineno
27
f.module
'program1A'
f.name
'stddev'


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
