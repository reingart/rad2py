# coding: utf8
# try something like

from statistics import calc_correlation, calc_significance, calc_linear_regression
   
def test_correlation():
    # test table [HUMPHREY95] p.514
    x_values = [186, 699, 132, 272, 291, 331, 199, 1890, 788, 1601]
    y_values = [15.0, 69.9, 6.5, 22.4, 28.4, 65.9, 19.4,198.7, 38.8, 138.2]

    r = calc_correlation(x_values, y_values)
    return {'r2': r**2}

def test_linear_regression():
    x_values = 10.0, 8.0, 13.0, 9.0, 11.0, 14.0, 6.0, 4.0, 12.0, 7.0, 5.0
    y_values = 8.04, 6.95, 7.58, 8.81, 8.33, 9.96, 7.24, 4.26, 10.84, 4.82, 5.68
    b0, b1 = calc_linear_regression(x_values, y_values)
    return {'b0': b0, 'b1': b1, 'ok': round(b0,2)==3.0 and round(b1,2)==0.5}

def get_projects_metrics():
    "Query size and time metrics series summarized by project"
    rows = db(db.psp_project.actual_loc!=None).select(db.psp_project.actual_loc, orderby=db.psp_project.project_id)
    actual_loc = [row.actual_loc for row in rows]
    rows = db(db.psp_project.project_id==db.psp_time_summary.project_id).select(db.psp_time_summary.actual.sum().with_alias("total"), groupby=db.psp_project.project_id, orderby=db.psp_project.project_id)
    hours = [row.total/60.0/60.0 for row in rows]
    return actual_loc, hours

def correlation():
    "Check correlation between actual object LOC and hours"
    # according [HUMPHREY95] p.513 & p.151:
    # - when 0.9 <= r2 : the relationship is considered predictive
    # - when 0.7 <= r2 < 0.9 : there is a strong correlation
    # - when 0.5 <= r2 < 0.7 : there is an adequate correlation (use with caution)
    # - when r2 < 0.5 : not reliable for planning purposes
    actual_loc, hours = get_projects_metrics()
    r = calc_correlation(actual_loc, hours)
    return {'loc': actual_loc, 'hours': hours, 'r2': r**2}
    
def significance():
    "Check the significance of a correlation"
    #TODO: test probability with student t
    # p = student_t(n-1, t) 
    # if 1-p<=0.05 data is considered good [HUMPHREY95] p.70 
    actual_loc, hours = get_projects_metrics()
    t, r2, n = calc_significance(actual_loc, hours)
    return {'loc': actual_loc, 'hours': hours, 'n': n, 'r2': r2, 't': t}


def get_time_todate():    
    "Calculate accumulated time per phase to date"    
    q = db.psp_project.project_id==db.psp_time_summary.project_id    
    rows = db(q).select(
            db.psp_time_summary.actual.sum().with_alias("subtotal"),
            db.psp_time_summary.phase,
            groupby=db.psp_time_summary.phase)
    total = float(sum([row.subtotal for row in rows], 0))
    todate = sorted([(row.psp_time_summary.phase, row.subtotal, row.subtotal/total) for row in rows],
                    key=lambda x: PSP_PHASES.index(x[0]))
    return todate

def time_in_phase():
    todate = get_time_todate()
    return {'todate': todate}


def time():
    "Estimate Time and Prediction Interval"
    # use historical data of actual object size (LOC) and time to calculate
    # development time based on planned LOC [HUMPHREY95] pp.153-155
    #TODO: calculate Upper and Lower Prediction Interval

    form = SQLFORM.factory(
            Field("size", "integer", comment="Planned size (estimated LOC)"),
            )
    
    if form.accepts(request.vars, session):
    
        # calculate regression parameters for historical LOC and tiem data:
        actual_loc, hours = get_projects_metrics()
        b0, b1 = calc_linear_regression(actual_loc, hours)

        # get LOC planned size and calculate development time
        size_k = form.vars.size
        time_t = b0 + b1*size_k
        
        return {'size_k': size_k, 'time_t': time_t}
        
    else:
        return {'form': form}


def linear_regression():
    "draw a linear regression chart"
    import pylab
    import matplotlib
    # clear graph
    matplotlib.pyplot.clf()
    matplotlib.use('Agg') 
    actual_loc, hours = get_projects_metrics()
    x = pylab.array(actual_loc)
    y = pylab.array(hours)
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
    pylab.savefig(response.body) 
    return response.body.getvalue()
