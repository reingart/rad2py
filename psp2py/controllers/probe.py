# coding: utf8
"PROxy Based size Estimation method"
# [HUMPHREY95] p.117

import math

from statistics import calc_standard_deviation, draw_normal_histogram


def categorize():
    # Calculate the Log-normal Object Size Ranges [HUMPHREY95] pp.129-131
    
    #TODO: group by category and class (methods)
    
    # 0. Fetch objects (functions or classes) in the reuse library:    
    objs = db(db.psp_reuse_library.id>0).select()
    objs = dict([(obj.function_name, dict(obj)) for obj in objs])
    # 1. Calculate the natural logarithm of LOC per function
    locs = {}
    for name, obj in objs.items():
        locs[name] = math.log(obj['loc'])
    # 2/3. Calculate the average and variance of the logarithmic values
    std_dev, avg_ln = calc_standard_deviation(locs.values())
    # PSP_SIZES = ["very small", "small", "medium", "large", "very large"]
    midpoints = {}
    for size, factor in zip(PSP_SIZES, [-2, -1, 0, +1, +2]):
        # 4. Calculate the logarithms of the size range midpoints:
        size_ln = avg_ln + factor * std_dev
        # 4. Take the antilogarithms to get range midpoints in LOC
        midpoints[size] = math.e**(size_ln)

    # Calculate object size distribution (

    return {'locs': locs.values(), "midpoints": midpoints}

def normal_distribution():
    "Draw the histogram of log-normal object size range"
    # this needs matplotlib!
    import pylab
    ret = categorize()
    locs = ret['locs']
    std_dev, avg = calc_standard_deviation(locs)
    x = [(loc - avg)/std_dev for loc in locs]
    bins = pylab.arange(-4,4,0.5)
    return draw_normal_histogram(x, bins, 'object frequency (reuse lib)', 'std_dev from the mean (log-nomal obj size)', response.body)

def get_loc_per_relative_size():
    loc = session.midpoints.get(request.vars.relative_size, "0")
    return """alert("LOC for %s = %s"); jQuery('#ajax_loc')[0].value=%s;""" % (request.vars.relative_size, int(loc), repr(int(loc)))

def get_loc_from_reuse_library():
    for obj in session.objs:
        if obj['function_name']==request.vars.function_name:
            loc = obj['loc']
            break
    else:
        loc = "0"
    return """alert("LOC for %s = %s"); jQuery('#ajax_loc')[0].value=%s;""" % (request.vars.function_name, int(loc), repr(int(loc)))


def index():
    "Identify objects to calculate projected LOC"
   
    if request.vars.finish:
        # done, redirect to 
        projected_loc = sum([obj['loc'] for obj in session.objects.values()])
        redirect(URL(c="estimate", f="index", vars={'planned_loc': projected_loc}))
        
    if session.midpoints is None or request.vars.reset:
        # reset initial data
        ret = categorize()
        session.midpoints = ret['midpoints']
        session.objects = {}
        session.objs = db(db.psp_reuse_library.id>0).select()
    
    form = FORM(TABLE(
        TR(TD(
            LABEL("Name", _for="name"), 
        ), TD(
            INPUT(_name="name", requires=IS_NOT_EMPTY(), ),
        ), TD(
            LABEL("based on", _for="function_name"),
        ), TD(
            SELECT([OPTION(obj['function_name']) for obj in session.objs], 
                   _name="function_name", 
                   _onclick="ajax('%s', ['function_name'], ':eval');" % URL('get_loc_from_reuse_library')),
        )),
        TR(TD(
            LABEL("Relative size", _for="relative_size"),
        ), TD(
            SELECT([OPTION(siz) for siz in PSP_SIZES], 
                   _name="relative_size", 
                   _onclick="ajax('%s', ['relative_size'], ':eval');" % URL('get_loc_per_relative_size')),
        ), TD(
            LABEL("Category", _for="category"),
        ), TD(
            SELECT([OPTION(cat) for cat in PSP_CATEGORIES], _name="category"),
        )),
        TR(TD(
            LABEL("Projected LOC", _for="loc"),
        ), TD(
            INPUT(_name="loc", _id="ajax_loc", 
                  _value=int(session.midpoints.get(PSP_SIZES[0])), 
                  requires=IS_INT_IN_RANGE(0,1000),
                  ),
        ), TD(
            INPUT(_type="submit"),
        ), TD(
            INPUT(_type="submit", _name="reset", _value="Reset"),
            " ",
            INPUT(_type="submit", _name="finish", _value="Finish"),
            _style="text-align: justify;",
        )),
        ))
    
    if form.accepts(request.vars, session, keepvalues=True):
        # store identified object in local object
        session.objects[form.vars.name] = form.vars
        
    return {'form': form, 'objects': session.objects}
