#!/usr/bin/env python
# coding:utf-8

"""PSP Program 1A - Standard Deviation
"""

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

import math


def mean(values):
    """Calculate the average of the numbers given:
    
    >>> mean([1, 2, 3])
    2.0
    >>> mean([1, 2])
    1.5
    >>> mean([1, 3])
    2.0
    """
    return sum(values) / float(len(values))


def stddev(values):
    """Calculate the standard deviation of a list of number values:
    
    >>> stddev([160, 591, 114, 229, 230, 270, 128, 1657, 624, 1503])
    572.026844746915
    >>> stddev([186, 699, 132, 272, 291, 331, 199, 1890, 788, 1601])
    625.6339806770231
    >>> stddev([15.0, 69.9, 6.5, 22.4, 28.4, 65.9, 19.4, 198.7, 38.8, 138.2])
    62.25583060601187
    """
    x_avg = mean(values)
    n = len(values)
    return math.sqrt(sum([(x_i - x_avg)**2 
                          for x_i in values]) / float(n - 1))


if __name__ == "__main__":
    # Table D5 "Object LOC" column
    sd = stddev([160, 591, 114, 229, 230, 270, 128, 1657, 624, 1503])
    assert round(sd, 2) == 572.03
    # Table D5 "New and Changed LOC" column
    sd = stddev([186, 699, 132, 272, 291, 331, 199, 1890, 788, 1601])
    assert round(sd, 2) == 625.63
    # Table D5 "Development Hours" column
    sd = stddev([15.0, 69.9, 6.5, 22.4, 28.4, 65.9, 19.4, 198.7, 38.8, 138.2])
    assert round(sd, 2) == 62.26

