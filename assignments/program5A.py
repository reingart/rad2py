#!/usr/bin/env python
# coding:utf-8

"PSP Program 5A - Numerical Integration"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

from math import e, pi, sqrt


def compute_integral(f, x_low, x_high, w, n):
    "Compute the numerical approximation of a definite integral"
    # composite simpson rule
    term1 = f(x_low)
    term2 = 0
    for j in xrange(1, n, 2):
        term2 += f(x_low + j * w)
    term3 = 0
    for j in xrange(2, n, 2):
        term3 += f(x_low + j * w)
    term4 = f(x_high)
    y = w / 3 * (term1 + 4 * term2 + 2 * term3 + term4)

    return y


def simpson_rule_integrate(f, x_low, x_high, error=0.00001):
    # 1. identify the upper and lower limits of the numerical integration
    if x_high < 0 and x_low == float("-infinity"):
        x_high = abs(x_high)
        x_low = 0
        p = -0.5
    elif x_low == float("-infinity"):
        x_low = 0
        p = 0.5
    # 2. select an initial number N and old result
    n = 20
    old_y = 0
    while True:
        # 3. divide the range to get the segment width
        w = (x_high - x_low) / n
        # 4. compute the numerical integration approximation
        y = compute_integral(f, x_low, x_high, w, n)
        # 5. compare with the old result if error is permisible
        if abs(y - old_y) <= error:
            if p > 0:
                return p + y
            else:
                return - p - y
        old_y = y
        # 6. double N
        n = 2 * n
        # 7. repeat ...


def factorial(x, step=1):
    "Calculate integer or float factorial (for gamma function, step=2)"
    if x > step:
        return x * factorial(x - step, step) / step
    return x / step


def gamma(n, d=2):
    "Calculate gamma function value for a fraction (numerator & denominator)"
    # WARNING: only tested for d=2 !
    if n % 2 != 0 and d == 2:
        return factorial(n - 2, step=2.0) * sqrt(pi)
    else:
        i = n / d
        return factorial(i - 1)


def simpson_rule_tests():
    "Calculate the probability values of the normal/t distribution"
    inf = float("infinity")

    # normal distribution
    f_normal_dist = lambda u: (1 / (2 * pi) ** (0.5)) * e ** ((- u ** 2) / 2)
    p = simpson_rule_integrate(f_normal_dist, - inf, -1.1)
    assert round(p, 4) == 0.1357
    p = simpson_rule_integrate(f_normal_dist, - inf, 2.5)
    assert round(p, 4) == 0.9938
    p = simpson_rule_integrate(f_normal_dist, - inf, 0.2)
    assert round(p, 4) == 0.5793

    # student t distribution
    n = 9   # degrees of freedom
    assert round(gamma(n, 2), 4) == 11.6317
    k = gamma(n + 1, 2) / (sqrt(n*pi) * gamma(n, 2))
    f_t_dist = lambda u: k * (1 + (u ** 2) / float(n)) ** (- (n +1) / 2)
    # WARNING: the Table A17 on [HUMPHREY95] pp.524 seems to be wrong...
    assert round(f_t_dist(0), 4) == 0.3880
    #assert round(f_t_dist(1), 4) == 0.3874
    #assert round(f_t_dist(2), 4) == 0.3854
    #assert round(f_t_dist(20), 4) == 0.2065
    p = simpson_rule_integrate(f_t_dist, - inf, 1.1)
    assert round(p, 4) == 0.8501


if __name__ == "__main__":
    simpson_rule_tests()
