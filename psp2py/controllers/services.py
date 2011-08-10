# coding: utf8
# try something like

from gluon.tools import Service
service = Service(globals())

def call():
    session.forget()
    return service()
    
response.generic_patterns = ['*.json', '*.html']

@service.jsonrpc
def get_projects(): 
    projects = db(db.psp_project.project_id>0).select()
    return [project.name for project in projects]

@service.jsonrpc
def save_project(project_name, defects): 
    project = db(db.psp_project.name==project_name).select()[0]
    db(db.psp_defect.project_id==project.project_id).delete()
    for defect in defects:
        defect['project_id'] = project.project_id
        if 'defect_id' in defect:
             del defect['defect_id']
        db.psp_defect.insert(**defect)
        
    return True

@service.jsonrpc
def load_project(project_name): 
    project = db(db.psp_project.name==project_name).select()[0]
    defects = db(db.psp_defect.project_id==project.project_id).select()       
    return defects, None


@service.jsonrpc
def add(a,b):
    return a+b
