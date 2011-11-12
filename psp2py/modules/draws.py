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


def draw_barchart(values, title, y_label, x_label, x_tick_labels, autolabel=False, text="", stacked=True, body=None):
    #!/usr/bin/env python
    # a bar plot with errorbars
    import pylab
    import matplotlib
    import numpy as np
    import matplotlib.pyplot as plt
    
    
    rects = []
    labels = []
    bottom = None     # for stacked bars
    
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ind = np.arange(len(values[0][3]))  # the x locations for the groups
    
    for i, (label, width, color, heights) in enumerate(values):
        labels.append(label)
        w = not stacked and width or 0
        rects.append(ax.bar(ind+w*i, heights, width, bottom=bottom, color=color))
        if stacked:
            bottom = [x + i for x, i in zip(bottom or [0]*len(heights), heights)]
    
    # add some
    ax.set_ylabel(y_label)
    ax.set_xlabel(x_label)
    ax.set_title(title)
    ax.set_xticks(ind+width/2.)
    ax.set_xticklabels( x_tick_labels )
    
    ax.legend( [r[0] for r in rects], labels, loc="best")
    
    def draw_autolabel(rects):
        # attach some text labels
        for rect in rects:
            height = rect.get_height()
            ax.text(rect.get_x()+rect.get_width()/2., 1.05*height, '%d'%int(height),
                    ha='center', va='bottom')

    if autolabel:
        for rect in rects:
            draw_autolabel(rect)

    pylab.grid(True)

    if text:
        plt.text(7.75, 27, text, size=12, rotation=0.,
             ha="center", va="center", 
             bbox = dict(boxstyle="round",
                         ec='black',
                         fc='w',
                         )
             )
    pylab.savefig(body) 
    return body.getvalue()


#Some simple functions to generate colours.
def pastel(colour, weight=2.4):
    """ Convert colour into a nice pastel shade"""
    from matplotlib.colors import colorConverter
    import numpy as np
    rgb = np.asarray(colorConverter.to_rgb(colour))
    # scale colour
    maxc = max(rgb)
    if maxc < 1.0 and maxc > 0:
        # scale colour
        scale = 1.0 / maxc
        rgb = rgb * scale
    # now decrease saturation
    total = sum(rgb)
    slack = 0
    for x in rgb:
        slack += 1.0 - x

    # want to increase weight from total to weight
    # pick x s.t.  slack * x == weight - total
    # x = (weight - total) / slack
    x = (weight - total) / slack

    rgb = [c + (x * (1.0-c)) for c in rgb]

    return rgb

def get_colours(n):
    """ Return n pastel colours. """
    import numpy as np
    import matplotlib
    base = np.asarray([[1,0,0], [0,1,0], [0,0,1]])

    if n <= 3:
        return base[0:n]

    # how many new colours to we need to insert between
    # red and green and between green and blue?
    needed = (((n - 3) + 1) / 2, (n - 3) / 2)

    colours = []
    for start in (0, 1):
        for x in np.linspace(0, 1, needed[start]+2):
            colours.append((base[start] * (1.0 - x)) +
                           (base[start+1] * x))

    return [pastel(c) for c in colours[0:n]]
