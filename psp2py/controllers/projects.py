# coding: utf8
# try something like

def index():
    return dict(form=crud.select(db.psp_project, linkto='show'))

def search():
    form, table=crud.search(db.psp_project, linkto='edit')
    return dict(form=form, table=table)
    
def create(): 
    return dict(form=crud.create(db.psp_project))
    
def show():
    project_id = request.args[1]
    project = db(db.psp_project.id==project_id).select().first()
    times = db(db.psp_time_summary.project_id==project_id).select(
        db.psp_time_summary.phase,
        db.psp_time_summary.plan,
        db.psp_time_summary.actual,
        db.psp_time_summary.interruption)
    defects = db(db.psp_defect.project_id==project_id).select(
        db.psp_defect.number,
        db.psp_defect.summary,
        db.psp_defect.type,
        db.psp_defect.inject_phase,
        db.psp_defect.remove_phase,
        db.psp_defect.fix_time,
        db.psp_defect.fix_defect,
    )
    form = crud.read(db.psp_project, project_id)
    return dict(project=project, form=form, times=times, defects=defects)

def edit():
    return dict(form=crud.update(db.psp_project, request.args[1]))
