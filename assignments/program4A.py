#!/usr/bin/env python
# coding:utf-8

"""PSP Program 4A - Linear Regression Parameter
"""

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"


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


def linear_regression(x_values, y_values):
    """Calculate the linear regression parameters for a set of n values

    >>> x = 10.0, 8.0, 13.0, 9.0, 11.0, 14.0, 6.0, 4.0, 12.0, 7.0, 5.0
    >>> y = 8.04, 6.95, 7.58, 8.81, 8.33, 9.96, 7.24, 4.26, 10.84, 4.82, 5.68
    >>> b0, b1 = linear_regression(x, y)
    >>> round(b0, 3)
    3.0
    >>> round(b1, 3)
    0.5
    >>> x = 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 8.0, 19.0, 8.0, 8.0, 8.0
    >>> y = 6.58, 5.76, 7.71, 8.84, 8.47, 7.04, 5.25, 12.50, 5.56, 7.91, 6.89
    >>> b0, b1 = linear_regression(x, y)
    >>> round(b0, 3)
    3.002
    >>> round(b1, 3)
    0.5

    """

    # calculate aux variables
    x_avg = mean(x_values)
    y_avg = mean(y_values)
    n = len(x_values)
    sum_xy = sum([(x_values[i] * y_values[i]) for i in range(n)])
    sum_x2 = sum([(x_values[i] ** 2) for i in range(n)])

    # calculate regression coefficients
    b1 = (sum_xy - (n * x_avg * y_avg)) / (sum_x2 - n * (x_avg ** 2))
    b0 = y_avg - b1 * x_avg

    return (b0, b1)


if __name__ == "__main__":
    # Table D8 "Size Estimating regression data"
    est_loc = [130, 650, 99, 150, 128, 302, 95, 945, 368, 961]
    est_new_chg_loc = [163, 765, 141, 166, 137, 355, 136, 1206, 433, 1130]
    act_new_chg_loc = [186, 699, 132, 272, 291, 331, 199, 1890, 788, 1601]
    # Estimated Object versus Actual New and changed LOC
    b0, b1 = linear_regression(est_loc, act_new_chg_loc)
    print b0, b1
    assert round(b0, 2) == -22.55
    assert round(b1, 4) == 1.7279
    # Estimated New and Changed LOC versus Actal and Changed LOC
    b0, b1 = linear_regression(est_new_chg_loc, act_new_chg_loc)
    assert round(b0, 2) == -23.92
    assert round(b1, 4) == 1.4310
    print b0, b1
