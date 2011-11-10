# coding: utf8
# try something like

from statistics import calc_correlation, calc_significance, calc_linear_regression, calc_student_t_probability
from draws import draw_linear_regression

   
def get_projects_metrics():
    "Query size and time metrics series summarized by project"
    q = db.psp_project.completed!=None     # only account finished ones!
    rows = db(q & (db.psp_project.actual_loc!=None)).select(db.psp_project.actual_loc, orderby=db.psp_project.project_id)
    actual_loc = [row.actual_loc for row in rows]
    rows = db(q & (db.psp_project.project_id==db.psp_time_summary.project_id)).select(db.psp_time_summary.actual.sum().with_alias("total"), groupby=db.psp_project.project_id, orderby=db.psp_project.project_id)
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
    r2 = r**2
    if 0.9 <= r2:
        corr = 'high (predictive)'
    elif 0.7 <= r2 < 0.9:
        corr = 'strong (planning)'
    elif 0.5 <= r2 < 0.7:
        corr = 'adequate (use with care)'
    elif r2 < 0.5:
        corr = 'weak (not reliable)'
    return {'loc': actual_loc, 'hours': hours, 'r2': r**2, 'correlation': corr}
    
def significance():
    "Check the significance of a correlation"
    #TODO: test probability with student t
    # p = student_t(n-1, t) 
    # if 1-p<=0.05 data is considered good [HUMPHREY95] p.70 
    actual_loc, hours = get_projects_metrics()
    t, r2, n = calc_significance(actual_loc, hours)
    p = calc_student_t_probability(t, n-1)
    return {'loc': actual_loc, 'hours': hours, 'n': n, 'r2': r2, 't': t, 'p': p, 's': 1-p}


def get_time_todate():    
    "Calculate accumulated time per phase to date"    
    q = db.psp_project.project_id==db.psp_time_summary.project_id
    q &= db.psp_project.completed!=None     # only account finished ones!
    rows = db(q).select(
            db.psp_time_summary.actual.sum().with_alias("subtotal"),
            db.psp_time_summary.phase,
            groupby=db.psp_time_summary.phase)
    total = float(sum([row.subtotal or 0 for row in rows], 0))
    todate = sorted([(row.psp_time_summary.phase, row.subtotal or 0, (row.subtotal or 0)/total*100.0) for row in rows],
                    key=lambda x: PSP_PHASES.index(x[0]))
    return todate

def time_in_phase():
    times = get_time_todate()
    return {'times': times}


def index():
    "Estimate Time and Prediction Interval (UPI, LPI)"
    # use historical data of actual object size (LOC) and time to calculate
    # development time based on planned LOC [HUMPHREY95] pp.153-155
    #TODO: calculate Upper and Lower Prediction Interval

    form = SQLFORM.factory(
            Field("size", "integer", 
                  default=request.vars.planned_loc,
                  comment="Planned size (estimated LOC)"),
            Field("project_id", db.psp_project, 
                  requires=IS_IN_DB(db, db.psp_project.project_id, "%(name)s"),
                  comment="Project to update plan"),
            )
    
    if form.accepts(request.vars, session):
    
        # calculate regression parameters for historical LOC and tiem data:
        actual_loc, hours = get_projects_metrics()
        b0, b1 = calc_linear_regression(actual_loc, hours)

        # get LOC planned size and calculate development time
        size_k = form.vars.size
        time_t = b0 + b1*size_k
        
        redirect(URL("update_plan", 
                     args=form.vars.project_id,
                     vars={'size_k': size_k, 'time_t': time_t, })
                     )
        
    return {'form': form}


def update_plan():
    "Get resource estimates (size and time) and update project plan summary"
    project_id = request.args[0]
    # get resources previously calculated
    estimated_loc = int(request.vars.size_k)
    estimated_time = float(request.vars.time_t)
    # summarize actual times in each pahse [(phase, to_date, to_date_%)]
    time_summary = get_time_todate()
    # subdivide time for each phase [HUMPHREY95] p.52
    # (according actual distribution of develpoment time)
    times = {}
    for phase, to_date, percentage in time_summary:
        times[phase] = estimated_time * percentage / 100.0
        
    for phase, plan in times.items():
        # convert plan time from hours to seconds
        plan = int(plan * 60 * 60)
        q = db.psp_time_summary.project_id==project_id
        q &= db.psp_time_summary.phase==phase
        # update current record
        cnt = db(q).update(plan=plan)
        if not cnt:
            # insert record if not exists
            db.psp_time_summary.insert(project_id=project_id, 
                                       phase=phase, 
                                       plan=plan, 
                                       actual=0, 
                                       interruption=0,
                                       )
    # update planned loc:
    db(db.psp_project.project_id==project_id).update(planned_loc=estimated_loc)
    # show project summary
    redirect(URL(c='projects', f='show', args=("psp_project", project_id)))


def linear_regression():
    "Draw the linear regression chart for actual loc and dev times"
    # this need matplotlib!
    import pylab
    actual_loc, hours = get_projects_metrics()
    x = pylab.array(actual_loc)
    y = pylab.array(hours)
    return draw_linear_regression(x, y, "Size (LOC)", "Time (hs)", response.body)
