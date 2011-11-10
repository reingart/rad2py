#!/usr/bin/env python


def draw_linear_regression(x, y, x_label, y_label, body):
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
    pylab.ylabel(y_label)
    pylab.xlabel(x_label)
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
