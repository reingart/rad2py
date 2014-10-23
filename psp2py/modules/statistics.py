#!/usr/bin/env python
# coding: utf8

import math
from integration import f_student_t_distribution, simpson_rule_integrate


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


def calc_standard_deviation(values):
    "Calculate the standard deviation of a list of number values"
    x_avg = mean(values)
    n = len(values)
    sd = math.sqrt(sum([(x_i - x_avg)**2 
                          for x_i in values]) / float(n))
    return sd, x_avg                      

def calc_student_t_probability(x, n):
    "Integrate t distribution from -infinity to x with n degrees of freedom"
    inf = float("infinity")
    p = simpson_rule_integrate(f_student_t_distribution(n), -inf, x)
    return p

def calc_double_sided_student_t_probability(t, n):
    "Calculate the p-value using a double sided student t distribution"
    # integrate a finite area from the origin to t
    p_aux = simpson_rule_integrate(f_student_t_distribution(n), 0, t)
    # return the area of the two tails of the distribution (symmetrical)
    return (0.5 - p_aux) * 2

def calc_double_sided_student_t_value(p, n):
    "Calculate the t-value using a double sided student t distribution"
    # replaces table lookup, thanks to http://statpages.org/pdfs.html
    v = dv = 0.5
    t = 0
    while dv > 0.000001:
        t = 1 / v - 1
        dv = dv / 2
        if calc_double_sided_student_t_probability(t, n) > p:
            v = v - dv
        else:
            v = v + dv
    return t


def calc_variance(x_values, y_values, b0, b1):
    "Calculate the mean square deviation of the linear regeression line"
    # take the variance from the regression line instead of the data average
    sum_aux = sum([(y - b0 - b1 * x) ** 2 for x, y in zip(x_values, y_values)])
    n = float(len(x_values))
    return (1 / (n - 2.0)) * sum_aux


def calc_prediction_interval(x_values, y_values, x_k, y_k, alpha):
    """Calculate the linear regression parameters for a set of n values
       then calculate the upper and lower prediction interval

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

    # calculate the t-value for the given alpha p-value
    t = calc_double_sided_student_t_value(1 - alpha, n - 2)

    # calculate the standard deviation
    sigma = math.sqrt(calc_variance(x_values, y_values, b0, b1))

    # calculate the range
    sum_xi_xavg = sum([(x - x_avg) ** 2 for x in x_values], 0.0)
    aux = 1 + (1 / float(n)) + ((x_k - x_avg) ** 2) / sum_xi_xavg
    p_range = t * sigma * math.sqrt(aux)

    # combine the range with the x_k projection:
    return b0, b1, p_range, y_k + p_range, y_k - p_range, t
