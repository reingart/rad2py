# coding: utf8

# Personal Software Process tables:

db.define_table("psp_project",
    Field("project_id", "id"),
    Field("name", "string"),
    Field("description", "string"),
    Field("requeriments", "text"),
    Field("testing", "text"),
    Field("user_id", db.auth_user),
    #Field("instructor_id", db.auth_user),
    Field("started", "date"),
    Field("completed", "date"),
    Field("planned_loc", "integer", comment="Total new & changed (estimated program size)"),
    Field("actual_loc", "integer", comment="Total new & changed (measured program size)"),
    Field("planned_time", "double", 
        comment=T("Original projected development time")),
    Field("time_lpi", "double", label=T("Time LPI"),
        comment="Total Time Lower Prediction Interval"),
    Field("time_upi", "double", label=T("Time UPI"),
        comment="Total Time Upper Prediction Interval"),
    format="%(name)s",
    )

PSP_PHASES = ["planning", "design", "code", "review", "compile", "test", "postmortem"]
PSP_TIMES = ["plan", "actual", "interruption"]

db.define_table("psp_time_summary",
    Field("id", "id"),
    Field("project_id", db.psp_project),
    Field("phase", "string", requires=IS_IN_SET(PSP_PHASES)),
    Field("plan", "integer"),
    Field("actual", "integer"),
    Field("interruption", "integer"),
    )

db.define_table("psp_comment",
    Field("id", "id"),
    Field("project_id", db.psp_project),
    Field("phase", "string", requires=IS_IN_SET(PSP_PHASES)),
    Field("message", "text"),
    Field("delta", "integer"),
    )

PSP_DEFECT_TYPES = {10: 'Documentation', 20: 'Synax', 30: 'Coding standard', 
    40: 'Assignment/Names', 50: 'Interface',  60: 'Checking', 70: 'Data', 
    80: 'Function', 90: 'System', 100: 'Enviroment'}
    
db.define_table("psp_defect",
    Field("id", "id"),
    Field("project_id", db.psp_project),
    Field("number", "integer"),
    Field("summary", "text"),
    Field("description", "text"),
    Field("date", "date"),
    Field("type", "string", requires=IS_IN_SET(PSP_DEFECT_TYPES)),
    Field("inject_phase", "string", requires=IS_IN_SET(PSP_PHASES)),
    Field("remove_phase", "string", requires=IS_IN_SET(PSP_PHASES)),
    Field("fix_time", "integer"),
    Field("fix_defect", "integer"),
    Field("filename", "string"),
    Field("lineno", "integer"),
    Field("offset", "integer"),
    Field("uuid", "string"),
    )


def pretty_time(counter):
    "return formatted string of a time count in seconds (days/hours/min/seg)"
    # find time unit and convert to it
    if counter is None:
        return ""
    counter = int(counter)
    for factor, unit in ((1., 's'), (60., 'm'), (3600., 'h')):
        if counter < (60 * factor):
            break
    # only print fraction if it is not an integer result
    if counter % factor:
        return "%0.2f %s" % (counter/factor, unit)
    else:
        return "%d %s" % (counter/factor, unit)

db.psp_time_summary.plan.represent = pretty_time
db.psp_time_summary.actual.represent = pretty_time
db.psp_time_summary.interruption.represent = pretty_time
db.psp_defect.fix_time.represent = pretty_time
db.psp_project.planned_time.represent = lambda x: x and ("%0.2f hs" % x) or ''
db.psp_project.time_upi.represent = lambda x: x and ("%0.2f hs" % x) or ''
db.psp_project.time_lpi.represent = lambda x: x and ("%0.2f hs" % x) or ''

# function/class type classification for easier reuse and estimation:
PSP_CATEGORIES = ["module", "model", "controller", "view"]
PSP_SIZES = ["very small", "small", "medium", "large", "very large"]

db.define_table("psp_reuse_library",
    Field("id", "id"),
    Field("project_id", db.psp_project),
    Field("filename", "string"),
    Field("class_name", "string"),
    Field("function_name", "string"),
    Field("category", "string", 
          requires=IS_IN_SET(PSP_CATEGORIES),
          default="module"),
    Field("lineno", "integer"),
    Field("loc", "integer"),
    )
