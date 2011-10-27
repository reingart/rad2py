#!/usr/bin/env python
# coding:utf-8

"Count LOC per class/method or function and detect new and modified lines"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"


import os.path
import pyclbr
from tokenize import generate_tokens, NEWLINE, COMMENT, INDENT, DEDENT

# Constants (for results lists)
LINENO = 0
CLASS = 1
FUNCTION = 2
LOC = 3

# WARNING: it seems that tokenize counts BOM as a logical line!


def find_functions_and_classes(modulename, path):
    """Parse the file and return [('lineno', 'class name', 'function')]
    
    >>> with open("test1.py", "w") as f:
    ...  f.write("def hola():\n pass\n#\ndef chau(): pass\n")
    ...  f.write("class Test:\n def __init__():\n\n  pass\n")
    >>> results = find_functions_and_classes("test1", ".")
    >>> results
    [[1, None, 'hola', 0], [3, None, 'chau', 0], [5, 'Test', '__init__', 0]]
    
    """
    # Assumptions: there is only one function/class per line (syntax)
    #              class attributes & decorators are ignored
    #              imported functions should be ignored
    #              inheritance clases from other modules is unhandled (super)doctest for results failed, exception NameError("name 'results' is not defined",)

    result = []
    module = pyclbr.readmodule_ex(modulename, path=path and [path])
    for obj in module.values():
        if isinstance(obj, pyclbr.Function) and obj.module == modulename:
            # it is a top-level global function (no class)
            result.append([obj.lineno, None, obj.name, 0])
        elif isinstance(obj, pyclbr.Class) and obj.module == modulename:
            # it is a class, look for the methods:
            for method, lineno in obj.methods.items():
                result.append([lineno, method, obj.name, 0])
    # sort using lineno:
    result.sort(key=lambda x: x[LINENO])
    return result


def get_object(objects, lineno):
    "Find the object at the lineno"
    obj = None
    ret = None
    for obj in objects:
        if obj[LINENO] > lineno:
            break
        ret = obj
    return ret


def count_logical_lines_per_object(filename, changes=None):
    """Count logical python lines and comments using Tokenizer, grouping
       line count per object (using find_functions_and_classes)
       changes is a dict of {lineno: 'new' or 'modified'}
       also returns new_lines and modified_lines count (logical lines)
    
    >>> with open("test1.py", "w") as f:
    ...  f.write("def hola():\n pass\n#\ndef chau(): pass\n")
    ...  f.write("class Test:\n def __init__():\n\n  pass\n")
    >>> results = count_logical_lines_per_object("test1.py")
    >>> results
    ([[1, None, 'hola', 1], [3, None, 'chau', 2], [5, 'Test', '__init__', 2]], 6, 1)
    """
    modulename = os.path.splitext(os.path.basename(filename))[0]
    path = os.path.dirname(filename)

    # total logical lines, new and modified count, comments qty
    locs = {'total': 0, 'new': 0, 'modified': 0, 'comments': 0}

    # get the objects, they must be sorted by lineno
    objects = find_functions_and_classes(modulename, path)
    obj = None  # current object
    indent = 0           # indentation
    base_indent = None   # current function/class indentation (block detection)
    with open(filename) as f:
        g = generate_tokens(f.readline)   # tokenize
        for toknum, tokval, start, end, line in g:
            srow, scol = start
            erow, ecol = end
            if toknum == INDENT:      # increment identation
                indent += 1
            elif toknum == DEDENT:    # decrement identation
                indent -= 1
                if base_indent is not None and indent <= base_indent:
                    base_indent = None
            if toknum == NEWLINE:  # count logical line:
                # get the next object for the current line
                obj = get_object(objects, srow)
                # store the indentation level (to detect when block is left)
                if obj and obj[LINENO] == srow:
                    base_indent = indent
                # sum the logical line (only if first line of obj reached)
                if obj and base_indent is not None:
                    obj[LOC] += 1
                locs['total'] += 1
                ##print "NEWLINE!", srow, erow 
                # check changes (relate physical to logical line)
                for lineno in range(srow, erow +1):
                    if lineno in changes:
                        change = changes[lineno]
                        locs[change] += 1   # count new or changed 
                        break   # check physical "multilines" only once
            if toknum == COMMENT:
                locs['comments'] += 1
    return objects, locs 

    
def analize_line_changes(old_lines, new_lines):
    "Diff and compare old and new line list to detect new and modified ones"
    import diffutil
    changes = diffutil.track_lines_changes(old_lines, new_lines, 
                                           modified_equals=True)

    # detect new lines and modified lines ret = {lineno: 'new' or 'modified'}
    # correct lineno (0-based for diffutil, 1-based for tokenize)
    ret = {}
    for old_lno, new_lno in changes:
        if new_lno is not None and old_lno is None:
            # new 
            ret[new_lno+1] = 'new'
        elif new_lno is not None and old_lno is not None:
            # equal or replace
            if old_lines[old_lno]==new_lines[new_lno]:
                pass
            else:
                ret[new_lno+1] = 'modified'
        else:
            # deleted, ignore
            pass 
    print "changes", ret
    return ret

if __name__ == "__main__":
    # tests:
    res = find_functions_and_classes("program1A", ".")
    print res
    assert res == [[14, None, 'mean', 0], [27, None, 'stddev', 0]]
    res = find_functions_and_classes("program2A", ".")
    print res
    assert res == [[16, None, 'count_logical_lines', 0], \
                   [40, None, 'logical_to_physical_count', 0]]
    res = count_logical_lines_per_object("program1A.py")
    print res
    assert res == ([[14, None, 'mean', 3], [27, None, 'stddev', 5]], 21, 5)
    res = count_logical_lines_per_object("program2A.py")
    print res
    assert res == ([[16, None, 'count_logical_lines', 12], 
                    [40, None, 'logical_to_physical_count', 41]], 73, 18)


