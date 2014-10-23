# coding: utf8
    

def index():
    "Calculate performance indicators"

    # Gather metrics:
    
    # Get total LOCs and Times
    
    q = db.psp_project.completed!=None     # only account finished ones!

    total_loc = db(q).select(
            db.psp_project.actual_loc.sum().with_alias("actual_loc_sum"),
            ).first().actual_loc_sum

    # Get times per phase
    q &= db.psp_project.project_id==db.psp_time_summary.project_id
    rows = db(q).select(
            db.psp_time_summary.actual.sum().with_alias("sum_actual"),
            db.psp_time_summary.plan.sum().with_alias("sum_plan"),
            db.psp_time_summary.plan.sum().with_alias("sum_interruption"),
            db.psp_time_summary.phase,
            groupby=db.psp_time_summary.phase)
    total_time = float(sum([row.sum_actual or 0 for row in rows], 0))
    times_per_phase = dict([(row.psp_time_summary.phase, row.sum_actual or 0) for row in rows])
    planned_time_per_phase = dict([(row.psp_time_summary.phase, row.sum_plan or 0) for row in rows])
    planned_time = float(sum([row.sum_plan or 0 for row in rows], 0))
    if total_time:
        cost_performance_index = planned_time / total_time
    else:
        cost_performance_index = 0
    interruption_time = float(sum([row.sum_interruption or 0 for row in rows], 0))

    # Get interruption time
    q &= db.psp_project.planned_time!=None
    rows = db(q).select(
            db.psp_time_summary.actual.sum().with_alias("subtotal"),
            )
    actual_time = float(sum([row.subtotal or 0 for row in rows], 0))

    
    # get defects per phase
    q = db.psp_project.completed!=None     # only account finished ones!
    q &= db.psp_project.project_id==db.psp_defect.project_id
    q &= db.psp_defect.type != 30     # ignore coding standard violations
    q &= db.psp_defect.remove_phase != ''     # ignore won't fix defects
    rows = db(q).select(
            db.psp_defect.id.count().with_alias("quantity"),
            db.psp_defect.fix_time.sum().with_alias("subtotal_fix_time"),
            db.psp_defect.inject_phase,
            db.psp_defect.remove_phase,
            groupby=(db.psp_defect.inject_phase,
                     db.psp_defect.remove_phase,))
    defects_injected_per_phase = dict([(phase, 0) for phase in PSP_PHASES])
    defects_removed_per_phase = dict([(phase, 0) for phase in PSP_PHASES])
    total_fix_time = 0
    for row in rows:
        defects_injected_per_phase[row.psp_defect.inject_phase] += row.quantity
        defects_removed_per_phase[row.psp_defect.remove_phase] += row.quantity
        total_fix_time += row.subtotal_fix_time
    
        
    # Calculate productivity measures
    loc_per_hour = total_loc / total_time * 60. * 60.

    # Calculare  YIELD (defects removed per phase)

    yields_per_phase = dict([(phase, 0) for phase in PSP_PHASES])
    escapes_per_phase = dict([(phase, 0) for phase in PSP_PHASES])
    for i, phase in enumerate(PSP_PHASES):
        removed = defects_removed_per_phase[phase]
        if i < len(PSP_PHASES) - 1:
            escapes = sum([defects_removed_per_phase[p] for p in PSP_PHASES[i+1:]])
        else:
            escapes = 0
        escapes_per_phase[phase] = escapes
        if escapes:
            yields_per_phase[phase] = round(100 * removed / float(removed + escapes), 2)

    # Calculate Process YIELD (removed before compile)
    
    i = PSP_PHASES.index("compile")
    removed = sum([defects_removed_per_phase[p] for p in PSP_PHASES[:i]])
    escapes = sum([defects_removed_per_phase[p] for p in PSP_PHASES[i:]])
    process_yield = round(100 * removed / float(removed + escapes), 2)

    # Calculate defect removal / injection rate
    total_defects_removed_per_hour = 0
    total_defects_injected_per_hour = 0
    for phase in PSP_PHASES:
        if defects_injected_per_phase.get(phase):
            total_defects_injected_per_hour += defects_injected_per_phase[phase]
        if defects_removed_per_phase.get(phase):
            total_defects_removed_per_hour += defects_removed_per_phase[phase]
    total_defect_count = total_defects_removed_per_hour
    total_defects_removed_per_hour /= float(total_time) / 60. / 60.
    total_defects_injected_per_hour /= float(total_time) / 60. / 60.
    average_fix_time = total_fix_time / total_defect_count
        
    # Calculare Defect Removal Leverage (DLR)
    defects_per_hour_per_phase = dict([(phase, None) for phase in PSP_PHASES])
    for phase in PSP_PHASES:
        if times_per_phase.get(phase):
            defects_per_hour_per_phase[phase] = defects_removed_per_phase[phase] / (times_per_phase[phase] / 60. / 60.)

    defect_removal_leverage = dict([(phase, None) for phase in PSP_PHASES])
    for phase in PSP_PHASES:
        if defects_per_hour_per_phase['test'] and defects_per_hour_per_phase[phase]:
            defect_removal_leverage[phase] = defects_per_hour_per_phase[phase] / defects_per_hour_per_phase['test']

    # Calculate defects / KLOC
    
    test_defects_per_kloc = defects_removed_per_phase['test'] / float(total_loc) * 1000
    total_defects_per_kloc = sum(defects_removed_per_phase.values()) / float(total_loc) * 1000

    # Calculate cost of quality (COQ)
    
    appraisal = 100 * (defects_per_hour_per_phase['review'] or 0) / total_time
    failure = 100 * (times_per_phase['compile'] + times_per_phase['test'])  / total_time
    cost_of_quality = appraisal + failure
    appraisal_failure_ratio = appraisal / failure
    

    return {
        'total_loc': total_loc, 
        'total_time': total_time, 
        'planned_time': planned_time, 
        'planned_time_per_phase': planned_time_per_phase,
        'interruption_time': interruption_time, 
        'cost_performance_index': cost_performance_index,
        'loc_per_hour': loc_per_hour,
        'total_defect_count': total_defect_count,
        'total_fix_time': total_fix_time,
        'average_fix_time': average_fix_time,
        'times_per_phase': times_per_phase,
        'yields_per_phase': yields_per_phase,
        'process_yield': process_yield,
        'total_defects_removed_per_hour': total_defects_removed_per_hour,
        'total_defects_injected_per_hour': total_defects_injected_per_hour,
        'defects_injected_per_phase': defects_injected_per_phase,
        'defects_removed_per_phase': defects_removed_per_phase, 
        'defects_per_hour_per_phase': defects_per_hour_per_phase,
        'defect_removal_leverage': defect_removal_leverage,
        'test_defects_per_kloc': test_defects_per_kloc,
        'total_defects_per_kloc': total_defects_per_kloc,
        'appraisal': appraisal,
        'failure': failure,
        'cost_of_quality': cost_of_quality,
        'appraisal_failure_ratio': appraisal_failure_ratio,
    }


def defects():
    "Defect Type Standard"
   
    # get defects per type
    q = db.psp_project.completed!=None     # only account finished ones!
    q &= db.psp_project.project_id==db.psp_defect.project_id
    q &= db.psp_defect.remove_phase != ''     # ignore won't fix defects
    rows = db(q).select(
            db.psp_defect.id.count().with_alias("quantity"),
            db.psp_defect.fix_time.sum().with_alias("subtotal_fix_time"),
            db.psp_defect.type.with_alias("defect_type"),
            groupby=(db.psp_defect.type,))
    total_fix_time = 0
    defect_count_per_type = dict([(t, 0) for t in PSP_DEFECT_TYPES])
    defect_fix_time_per_type = dict([(t, 0) for t in PSP_DEFECT_TYPES])
    for row in rows:
        defect_count_per_type[int(row.defect_type)] += int(row.quantity)
        defect_fix_time_per_type[int(row.defect_type)] += float(row.subtotal_fix_time)
        total_fix_time += row.subtotal_fix_time
    defect_count = sum(defect_count_per_type.values())
    
    PSP_DEFECT_DESC = {
        10: 'Errors in docstrings and comments',
        20: 'SyntaxError (spelling, punctuation, format) and IndentationError (block delimitation)',
        30: 'PEP8 format warnings and errors (long lines, missing spaces, etc.)',
        40: 'NameError (undefined), unused variables, IndexError/KeyError (range/limits LookupError) and UnboundLocalError (scope)',
        50: 'TypeError, AttributeError: wrong parameters and methods',
        60: 'AssertionError (failed assert) and doctests',
        70: 'ValueError (wrong data) and ArithmeticError (overflow, zero-division, floating-point)',
        80: 'RuntimeError and logic errors',
        90: 'SystemError and Libraries or package unexpected errors',
        100: 'EnvironmentError: Operating system and build/third party unexpected errors',
        }

    
    return {
        'total_fix_time': total_fix_time,
        'defect_count': defect_count,
        'defect_count_per_type': defect_count_per_type,
        'defect_fix_time_per_type': defect_fix_time_per_type,
        'PSP_DEFECT_DESC': PSP_DEFECT_DESC,
    }


def pareto_distribution():
    "Pareto distribution barchart of Defects Types"
    from draws import draw_barchart

    # get defects per type by remove_phase
    q = db.psp_project.completed!=None     # only account finished ones!
    q &= db.psp_project.project_id==db.psp_defect.project_id
    q &= db.psp_defect.remove_phase != ''     # ignore won't fix defects
    rows = db(q).select(
            db.psp_defect.id.count().with_alias("quantity"),
            db.psp_defect.type.with_alias("defect_type"),
            db.psp_defect.remove_phase.with_alias("remove_phase"),
            groupby=(db.psp_defect.type, db.psp_defect.remove_phase))
    # dict: (defect_type: [missed, found]
    defect_count_per_type = dict([(t, [0, 0]) for t in PSP_DEFECT_TYPES])
    defect_count = 0
    for row in rows:
        # detect if the defect was found in review (before compile)
        if PSP_PHASES.index("compile") <= PSP_PHASES.index(row.remove_phase):
            defect_count_per_type[int(row.defect_type)][0] += int(row.quantity)
        else:
            defect_count_per_type[int(row.defect_type)][1] += int(row.quantity)
        defect_count += int(row.quantity)

    bars = []

    for defect_type, (missed, found) in defect_count_per_type.items():
        bars.append((defect_type, missed / float(defect_count) * 100., found / float(defect_count) * 100.))
    
    # sort types by percentage of defect descendent order:
    bars.sort(key=lambda x: x[1]+x[2], reverse=True)
    
    x_tick_labels = [bar[0] for bar in bars]
    x_heights_missed = [bar[1] for bar in bars]
    x_heights_found = [bar[2] for bar in bars]
    
    title = "Defects missed in Code Review"
    y_label = "Percentage of Defects"
    x_label = "Defect Type Category"
    
    values = [("Missed", 0.35, 'r', x_heights_missed),
              ("Found", 0.35, 'y', x_heights_found),]
    
    text = '\n'.join(["%s: %s" % (k, v) for k,v in sorted(PSP_DEFECT_TYPES.items())])
    
    if request.extension == "html":
        return {"values": values, "title": title, "y_label": y_label, "x_tick_labels": x_tick_labels}  
    else:
        return draw_barchart(values, title, y_label, x_label, x_tick_labels,
                             text=text,
                             autolabel=False, 
                             body=request.body)


def average_fix_time():
    "Average fix time barchart of Defects Types per Phase"
    from draws import draw_barchart, get_colours

    # get defects per type by remove_phase
    q = db.psp_project.completed!=None     # only account finished ones!
    q &= db.psp_project.project_id==db.psp_defect.project_id
    q &= db.psp_defect.remove_phase != ''     # ignore won't fix defects
    rows = db(q).select(
            db.psp_defect.id.count().with_alias("quantity"),
            db.psp_defect.type.with_alias("defect_type"),
            db.psp_defect.fix_time.sum().with_alias("subtotal_fix_time"),
            db.psp_defect.remove_phase.with_alias("remove_phase"),
            groupby=(db.psp_defect.type, db.psp_defect.remove_phase))
    # dict: (defect_type: [missed, found]
    fixtime_per_phase_per_type = dict([(t, dict([(p, 0) for p in PSP_PHASES])) for t in PSP_DEFECT_TYPES])
    defect_count_per_type = dict([(t, 0) for t in PSP_DEFECT_TYPES])
    for row in rows:
        # detect if the defect was found in review (before compile)
        fixtime_per_phase_per_type[int(row.defect_type)][row.remove_phase] += int(row.subtotal_fix_time)
        defect_count_per_type[int(row.defect_type)] += int(row.quantity)
    bars = []

    colours = get_colours(len(PSP_DEFECT_TYPES))
    values = []
    for defect_type, colour in zip(sorted(PSP_DEFECT_TYPES), colours):
        heights = []
        for phase in PSP_PHASES:
            if defect_count_per_type[defect_type]:
                avg = fixtime_per_phase_per_type[defect_type][phase]/float(defect_count_per_type[defect_type])/60.
            else:
                avg = 0
            heights.append(avg)
        values.append((PSP_DEFECT_TYPES[defect_type], 0.09, colour, heights))
         
    x_tick_labels = [p for p in PSP_PHASES]
    
    title = "Average Fix Time"
    y_label = "Average Fix Time (minutes)"
    x_label = "Phase"
    
    if request.extension == "html":
        return {"values": values, "title": title, "y_label": y_label, "x_tick_labels": x_tick_labels}  
    else:
        return draw_barchart(values, title, y_label, x_label, x_tick_labels,
                             stacked=False,
                             autolabel=False, 
                             body=request.body)


def projects():

    q = db.psp_project.project_id==db.psp_time_summary.project_id
    rows = db(q).select(
            db.psp_time_summary.actual.sum().with_alias("sum_actual"),
            db.psp_time_summary.plan.sum().with_alias("sum_plan"),
            db.psp_time_summary.plan.sum().with_alias("sum_interruption"),
            db.psp_project.ALL,
            groupby=db.psp_project.ALL)
    total_time = float(sum([row.sum_actual or 0 for row in rows], 0))
    planned_time = float(sum([row.sum_plan or 0 for row in rows], 0))
    interruption_time = float(sum([row.sum_interruption or 0 for row in rows], 0))

    projects = rows

    # get defects per project
    q = db.psp_project.project_id==db.psp_defect.project_id
    q &= db.psp_defect.remove_phase != ''     # ignore won't fix defects
    rows = db(q).select(
            db.psp_defect.id.count().with_alias("quantity"),
            db.psp_defect.fix_time.sum().with_alias("subtotal_fix_time"),
            db.psp_defect.project_id.with_alias("project_id"),
            groupby=(db.psp_defect.project_id,))
    total_fix_time = 0
    defects_per_project = {}
    fix_time_per_project = {}
    for row in rows:
        defects_per_project[row.project_id] = defects_per_project.get(row.project_id, 0) + int(row.quantity)
        fix_time_per_project[row.project_id] = fix_time_per_project.get(row.project_id, 0) + float(row.subtotal_fix_time)
        total_fix_time += row.subtotal_fix_time
    defect_count = sum(defects_per_project.values())


    return {
        'projects': projects,
        'total_time': total_time,
        'planned_time': planned_time,
        'defects_per_project': defects_per_project,
        'fix_time_per_project': fix_time_per_project,
    }
