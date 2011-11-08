# coding: utf8
# try something like
import math

def calc_correlation(x_values, y_values):
    
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

def test_correlation():
    # test table p.514
    x_values = [186, 699, 132, 272, 291, 331, 199, 1890, 788, 1601]
    y_values = [15.0, 69.9, 6.5, 22.4, 28.4, 65.9, 19.4,198.7, 38.8, 138.2]

    r = calc_correlation(x_values, y_values)
    return {'r2': r**2}

def get_projects_metrics():

    rows = db(db.psp_project.actual_loc!=None).select(db.psp_project.actual_loc, orderby=db.psp_project.project_id)
    actual_loc = [row.actual_loc for row in rows]
    rows = db(db.psp_project.project_id==db.psp_time_summary.project_id).select(db.psp_time_summary.actual.sum().with_alias("total"), groupby=db.psp_project.project_id, orderby=db.psp_project.project_id)
    hours = [row.total for row in rows]
    return actual_loc, hours
    
def correlation():
    "Check correlation between actual object LOC and hours"
       
    actual_loc, hours = get_projects_metrics()
    r = calc_correlation(actual_loc, hours)
    return {'loc': actual_loc, 'hours': hours, 'r2': r**2}
    
def significance():
    
    actual_loc, hours = get_projects_metrics()
    
    n = len (hours)
    r = calc_correlation(actual_loc, hours)
    r2 = r**2
    t = abs(r)*math.sqrt(n - 2)/math.sqrt(1 - r**2)
    return {'loc': actual_loc, 'hours': hours, 'n': n, 'r2': r2, 't': t}
