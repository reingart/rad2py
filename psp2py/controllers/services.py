# coding: utf8
# try something like

from gluon.tools import Service
service = Service(globals())

def call():
    session.forget()
    return service()
    
response.generic_patterns = ['*.json', '*.html']

def get_project_id(project_name):
    "Find the project and create a new one if it doesn't exists"
    project = db(db.psp_project.name==project_name).select().first()
    if project:
        project_id = project.project_id
    else:
        project_id = db.psp_project.insert(name=project_name)
    return project_id

@service.jsonrpc
def get_projects(): 
    projects = db(db.psp_project.project_id>0).select()
    return [project.name for project in projects]

@service.jsonrpc
def save_project(project_name, defects, time_summaries, comments): 
    project_id = get_project_id(project_name)

    # clean and store defects:
    db(db.psp_defect.project_id==project_id).delete()
    for defect in defects:
        defect['project_id'] = project_id
        defect.pop("id", None)
        defect.pop("defect_id", None)
        db.psp_defect.insert(**defect)

    # clean and store time summaries:
    db(db.psp_time_summary.project_id==project_id).delete()
    for time_summary in time_summaries:
        time_summary['project_id'] = project_id
        if 'id' in time_summary:
             del time_summary['id']
        db.psp_time_summary.insert(**time_summary)

    # clean and store comments:
    db(db.psp_comment.project_id==project_id).delete()
    for comment in comments:
        comment['project_id'] = project_id
        if 'id' in comment:
             del comment['id']
        db.psp_comment.insert(**comment)

    return True

@service.jsonrpc
def load_project(project_name): 
    project_id = get_project_id(project_name)
    defects = db(db.psp_defect.project_id==project_id).select()
    time_summaries = db(db.psp_time_summary.project_id==project_id).select()
    comments = db(db.psp_comment.project_id==project_id).select()
    return defects, time_summaries, comments

    
@service.jsonrpc
def update_project(project_name, actual_loc, reuse_library_entries): 
    "Update counted LOC and reuse library entries (postmortem)"

    project_id = get_project_id(project_name)

    # update total loc counted:
    if project:
        db(db.psp_project.project_id==project_id).update(actual_loc=actual_loc)

    # clean and store reuse library entries:
    if project:
        db(db.psp_reuse_library.project_id==project_id).delete()
    for entry in reuse_library_entries:
        entry['project_id'] = project_id
        db.psp_reuse_library.insert(**entry)

    return True
