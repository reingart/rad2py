#!/usr/bin/env python
# coding: utf8

import math


def mean(values):
    "Calculate the average of the numbers given"
    return sum(values) / float(len(values))
    

def calc_correlation(x_values, y_values):
    "Calculate strength of a relationship between two sets of data"
    # calculate aux variables
    n = len(x_values)       
    sum_xy = sum([(x_values[i] * y_values[i]) for i in range(n)])
    sum_x = sum([(x_values[i]) for i in range(n)])
    sum_y = sum([(y_values[i]) for i in range(n)])
    sum_x2 = sum([(x_values[i] ** 2) for i in range(n)])
    sum_y2 = sum([(y_values[i] ** 2) for i in range(n)])

    # calculate corelation
    r = (n * sum_xy - (sum_x * sum_y)) / math.sqrt((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2))

    return r


def calc_significance(x_values, y_values):
    "Calculate the significance (likelihood of two set of data correlation)"
    n = len (x_values)
    r = calc_correlation(x_values, y_values)
    r2 = r**2
    t = abs(r)*math.sqrt(n - 2)/math.sqrt(1 - r**2)
    return t, r2, n


def calc_linear_regression(x_values, y_values):
    "Calculate the linear regression parameters for a set of n values"

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
