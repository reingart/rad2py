#!/usr/bin/env python
# coding:utf-8

"PSP Program 6A - Linear Regression Prediction Interval"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"


from math import sqrt, pi

# reuse previos programs
from program1A import mean
from program5A import simpson_rule_integrate, gamma


def double_sided_student_t_probability(t, n):
    "Calculate the p-value using a double sided student t distribution"
    # create the function for n degrees of freedom:
    k = gamma(n + 1, 2) / (sqrt(n * pi) * gamma(n, 2))
    f_t_dist = lambda u: k * (1 + (u ** 2) / float(n)) ** (- (n + 1) / 2.0)
    # integrate a finite area from the origin to t
    p_aux = simpson_rule_integrate(f_t_dist, 0, t)
    # return the area of the two tails of the distribution (symmetrical)
    return (0.5 - p_aux) * 2


def double_sided_student_t_value(p, n):
    "Calculate the t-value using a double sided student t distribution"
    # replaces table lookup, thanks to http://statpages.org/pdfs.html
    v = dv = 0.5
    t = 0
    while dv > 0.000001:
        t = 1 / v - 1
        dv = dv / 2
        if double_sided_student_t_probability(t, n) > p:
            v = v - dv
        else:
            v = v + dv
    return t


def variance(x_values, y_values, b0, b1):
    "Calculate the mean square deviation of the linear regerssion line"
    # take the variance from the regression line instead of the data average
    sum_aux = sum([(y - b0 - b1 * x) ** 2 for x, y in zip(x_values, y_values)])
    n = float(len(x_values))
    return (1 / (n - 2.0)) * sum_aux


def prediction_interval(x_values, y_values, x_k, alpha):
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
    t = double_sided_student_t_value(1 - alpha, n - 2)

    # calculate the standard deviation
    sigma = sqrt(variance(x_values, y_values, b0, b1))

    # calculate the range
    sum_xi_xavg = sum([(x - x_avg) ** 2 for x in x_values], 0.0)
    aux = 1 + (1 / float(n)) + ((x_k - x_avg) ** 2) / sum_xi_xavg
    p_range = t * sigma * sqrt(aux)

    # combine the range with the x_k projection:
    return b0, b1, p_range, x_k + p_range, x_k - p_range, t


def test_student_t_integration():
    # test student t values
    assert round(double_sided_student_t_probability(t=1.8595, n=8), 4) == 0.1
    assert round(double_sided_student_t_value(p=0.1, n=8), 4) == 1.8595


if __name__ == "__main__":
    test_student_t_integration()
    # Table D8 "Size Estimating regression data"
    est_loc = [130, 650, 99, 150, 128, 302, 95, 945, 368, 961]
    act_new_chg_loc = [186, 699, 132, 272, 291, 331, 199, 1890, 788, 1601]
    projection = 644.429
    # 70 percent
    b0, b1, p_range, upi, lpi, t = prediction_interval(
            est_loc, act_new_chg_loc, projection, alpha=0.7)
    print "70% Prediction interval: ", b0, b1, p_range, upi, lpi, t
    assert round(t, 3) == 1.108
    assert round(b0, 2) == -22.55
    assert round(b1, 4) == 1.7279
    assert round(p_range, 3) == 236.563
    assert round(upi, 2) == 880.99
    assert round(lpi, 2) == 407.87
    # 90 percent
    b0, b1, p_range, upi, lpi, t = prediction_interval(
            est_loc, act_new_chg_loc, projection, alpha=0.9)
    print "90% Prediction interval: ", b0, b1, p_range, upi, lpi, t
    assert round(t, 2) == 1.86
    assert round(p_range, 2) == 396.97
    assert round(upi, 2) == 1041.4
    assert round(lpi, 2) == 247.46

