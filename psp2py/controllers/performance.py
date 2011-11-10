# coding: utf8
    

def index():
    "Calculate performance indicators"

    # Gather metrics:
    
    # Get total LOCs
    
    q = db.psp_project.completed!=None     # only account finished ones!

    total_loc = db(q).select(
            db.psp_project.actual_loc.sum().with_alias("actual_loc_sum"),
            ).first().actual_loc_sum

    # Get times per phase
    q &= db.psp_project.project_id==db.psp_time_summary.project_id
    rows = db(q).select(
            db.psp_time_summary.actual.sum().with_alias("subtotal"),
            db.psp_time_summary.phase,
            groupby=db.psp_time_summary.phase)
    total_time = float(sum([row.subtotal or 0 for row in rows], 0))
    times_per_phase = dict([(row.psp_time_summary.phase, row.subtotal or 0) for row in rows])
    
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
        'loc_per_hour': loc_per_hour,
        'total_defect_count': total_defect_count,
        'total_fix_time': total_fix_time,
        'average_fix_time': average_fix_time,
        'times_per_phase': times_per_phase,
        'yields_per_phase': yields_per_phase,
        'process_yield': process_yield,
        'total_defects_removed_per_hour': total_defects_removed_per_hour,
        'total_defects_injected_per_hour': total_defects_injected_per_hour,
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
