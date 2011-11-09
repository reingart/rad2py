# coding: utf8

from statistics import calc_correlation, calc_significance, calc_linear_regression, calc_student_t_probability

# test TABLE A12 [HUMPHREY95] p.514
x_values = [186, 699, 132, 272, 291, 331, 199, 1890, 788, 1601]
y_values = [15.0, 69.9, 6.5, 22.4, 28.4, 65.9, 19.4,198.7, 38.8, 138.2]
   
def correlation():
    r = calc_correlation(x_values, y_values)
    return {'r2': r**2, 'ok': round(r**2, 4)==0.9107}

def linear_regression():
    b0, b1 = calc_linear_regression(x_values, y_values)
    return {'b0': b0, 'b1': b1, 'ok': round(b0,3)==-0.351 and round(b1,3)==0.095}

def significance():
    # [HUMPHREY95] p.515
    t, r2, n = calc_significance(x_values, y_values)
    p = calc_student_t_probability(t, n-1)
    return {'loc': x_values, 'hours': y_values, 'n': n, 'r2': r2, 't': t, 'ok': round(t, 4)==9.0335, 'p': p}
