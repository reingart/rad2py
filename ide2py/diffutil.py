#!/usr/bin/env python
# coding:utf-8

"Diff facilities enhancing python stdlib (difflib.SequenceMatcher)"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"


import difflib


class FancySequenceMatcher(difflib.SequenceMatcher):
    """Adapted SM that splits 'replace' block detecting the modified line
    (based on difflib.Diffier but returning opcodes instead of text lines)
    
    Example:

    >>> s = FancySequenceMatcher(None,
    ...     "private Thread currentThread difflib;b a".split(),
    ...     "alas priVate volatile Thread currentThread difflib;".split())
    >>>

    >>> for opcode in s.get_opcodes():
    ...     print "%6s a[%d:%d] b[%d:%d]" % opcode
    insert a[0:0] b[0:1]
    replace a[0:1] b[1:2]
    insert a[1:1] b[2:3]
     equal a[1:3] b[3:5]
    replace a[3:4] b[5:6]
    delete a[4:5] b[6:6]

    For the sake of comparison, original SequenceMatcher only detect replaces
    >>> for opcode in difflib.SequenceMatcher.get_opcodes(s):
    ...     print "%6s a[%d:%d] b[%d:%d]" % opcode
    replace a[0:1] b[0:3]
     equal a[1:3] b[3:5]
    replace a[3:5] b[5:6]

    """ 

    BEST_RATIO = 0.74   # start similarity comparation score
    CUTOFF = 0.75       # synch up similarity score 
    
    def get_opcodes(self):
        a, b = self.a, self.b
        for tag, alo, ahi, blo, bhi in difflib.SequenceMatcher.get_opcodes(self):
            if tag != "replace" or ahi-alo==bhi-blo:
                yield tag, alo, ahi, blo, bhi
            else:
                for ops in self._fancy_replace(a, alo, ahi, b, blo, bhi):
                    yield ops
    
    def _fancy_replace(self, a, alo, ahi, b, blo, bhi):
        "Search 'replace' block for *similar* lines (synch point)"
        best_ratio = self.BEST_RATIO
        eqi, eqj = None, None   # 1st indices of equal lines (if any)
    
        # several lines, find modified lines (not inserted/deleted)
        cruncher = difflib.SequenceMatcher(self.isjunk)
        for j in xrange(blo, bhi):
            bj = b[j]
            cruncher.set_seq2(bj)
            for i in xrange(alo, ahi):
                ai = a[i]
                if ai == bj:
                    if eqi is None:
                        eqi, eqj = i, j
                    continue
                cruncher.set_seq1(ai)
                # check if lines are similar (optimized):
                if cruncher.real_quick_ratio() > best_ratio and \
                      cruncher.quick_ratio() > best_ratio and \
                      cruncher.ratio() > best_ratio:
                    best_ratio, best_i, best_j = cruncher.ratio(), i, j
        if best_ratio < self.CUTOFF:
            # no non-identical "pretty close" pair
            if eqi is None:
                # no identical pair either -- treat it as a straight replace
                # (use equal index blo,blo, ahi,ahi to signal empty lines)
                yield 'delete', alo, ahi, blo, blo
                yield 'insert', ahi, ahi, blo, bhi                
                return
            # no close pair, but an identical pair -- synch up on that
            best_i, best_j, best_ratio = eqi, eqj, 1.0
        else:
            # there's a close pair, so forget the identical pair (if any)
            eqi = None

        # a[best_i] very similar to b[best_j]; eqi is None if they're not equal

        # pump out diffs from before the synch point
        for ops in self._fancy_helper(a, alo, best_i, b, blo, best_j):
            yield ops

        if eqi is None:
            # pump out the synched lines
            yield 'replace', best_i, best_i+1, best_j, best_j+1
        else:
            # the synch pair is identical
            yield 'equal', best_i, best_i+1, best_j, best_j+1

        # pump out diffs from after the synch point
        for ops in self._fancy_helper(a, best_i+1, ahi, b, best_j+1, bhi):
            yield ops
                               
    def _fancy_helper(self, a, alo, ahi, b, blo, bhi):
        "split ops block (to and from a synch line)"
        g = []
        if alo < ahi:
            if blo < bhi:
                for ops in self._fancy_replace(a, alo, ahi, b, blo, bhi):        
                    yield ops
                #yield 'replace', alo, ahi, blo, bhi
            else:
                yield 'delete', alo, ahi, blo, blo
        elif blo < bhi:
            yield 'insert', ahi, ahi, blo, bhi
        else:
            pass # discard alo == ahi  blo == bhi

    def _intraline_diffs(self, a, b):
        "intraline difference marking"
        atags = btags = ""
        cruncher = difflib.SequenceMatcher(self.isjunk)
        cruncher.set_seqs(a, b)
        
        # check if lines are similar (avoid multiple small changes):
        if cruncher.real_quick_ratio() >= self.CUTOFF and \
              cruncher.quick_ratio() >= self.CUTOFF and \
              cruncher.ratio() >= self.CUTOFF:

            for tag, ai1, ai2, bj1, bj2 in cruncher.get_opcodes():
                if tag != 'equal':
                    yield (ai1, ai2), (bj1, bj2)


def track_lines_changes(old, new, modified_equals=False):
    """Compare items (lines), return a list of tuples (old_linenno, new_linenno)
    modified_equals controls whether replace are treated like insert or equal
    (in that case, to detect modifications, related lines should be compared)

    >>> print track_lines_changes("a b c d".split(), "a 1 b 2 d e".split())
    [(0, 0), (None, 1), (1, 2), (None, 3), (3, 4), (None, 5)]
    >>> print track_lines_changes("a b c d".split(), "a 1 b 2 d e".split(), modified_equals=True)
    [(0, 0), (None, 1), (1, 2), (2, 3), (3, 4), (None, 5)]
    """
    s = FancySequenceMatcher(None, old, new)
    ret = []
    for opcode, alo, ahi, blo, bhi in s.get_opcodes():
        #print "%6s a[%d:%d] b[%d:%d]" % (opcode, ahi, ahi, blo, bhi), old[alo:ahi], new[blo:bhi]
        if opcode == "insert":
            for lno in range(blo, bhi):
                ret.append((None, lno))
        if opcode == "replace" and not modified_equals:
            for lno in range(blo, bhi):
                ret.append((None, lno))
        if opcode == "equal" or (opcode == "replace" and modified_equals):
            old_lno = range(alo, ahi)
            for i, lno in enumerate(range(blo, bhi)):
                ret.append((old_lno[i], lno))
        if opcode == "delete":
            for i, lno in enumerate(range(alo, ahi)):
                ret.append((lno, None))
    return ret

def _test():
    
    import doctest, diffutil
    return doctest.testmod(diffutil)




if __name__ == "__main__":
    _test()

