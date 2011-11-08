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


def calc_standard_deviation(values):
    "Calculate the standard deviation of a list of number values"
    x_avg = mean(values)
    n = len(values)
    sd = math.sqrt(sum([(x_i - x_avg)**2 
                          for x_i in values]) / float(n - 1))
    return sd, x_avg                      

def draw_linear_regression(x, y, body):
    "Plot a linear regression chart"
    # x and y are matplotlib pylab arrays, body is a StringIO
    import pylab
    import matplotlib
    # clear graph
    matplotlib.pyplot.clf()
    matplotlib.use('Agg') 
    #nse = 0.3 * pylab.randn(len(x))
    #y = 2 + 3 * x + nse
    # the best fit line from polyfit ; you can do arbitrary order
    # polynomials but here we take advantage of a line being a first order 
    # polynomial
    m, b = pylab.polyfit( x , y , 1 )
    # plot the data with blue circles and the best fit with a thick
    # solid black line
    pylab.plot(x, y, 'bo ', x, m * x+b , '-k' , linewidth=2)
    pylab.ylabel('Time (Hs)')
    pylab.xlabel('LOC')
    pylab.grid(True)
    pylab.savefig(body) 
    return body.getvalue()
    
def draw_normal_histogram(x, bins, y_label='', x_label='', body=""):
    "Plot a histogram chart"
    # x are matplotlib pylab arrays, body is a StringIO
    import pylab
    import matplotlib
    # clear graph
    matplotlib.pyplot.clf()
    matplotlib.use('Agg') 
    n, bins1, patches = pylab.hist(x, bins, histtype='bar', facecolor='green', alpha=0.75)
    #pylab.setp(patches, 'facecolor', 'g', 'alpha', 0.75)
    pylab.ylabel(y_label)
    pylab.xlabel(x_label)
    # add a line showing the expected distribution
    mu = pylab.mean(x)
    sigma = pylab.std(x)
    y = pylab.normpdf(bins, mu, sigma)
    l = pylab.plot(bins, y, 'k--', linewidth=1.5)

    
    pylab.grid(True)
    pylab.savefig(body) 
    return body.getvalue()
