# coding: utf8

# simple wiki functionalities

def index(): 
    "List all pages"
    rows = db(db.wiki.id>0).select(db.wiki.page, db.wiki.title)
    return dict(rows=rows)
    
def view():
    "Show a page"
    if not request.args:
        page = 'index'
    else:
        page = '/'.join(request.args)
    
    rows = db(db.wiki.page==page).select()

    if rows:
        text = MARKMIN(rows[0].text)
        title = rows[0].title
    else:
        text = T('page not found!')
        title = page
    
    return dict(text=text, title=title)

def load():
    "Show basic html view for GUI IDE"
    return view()

def edit():
    "Edit/Create a page"
    if request.args:
        page = '/'.join(request.args)
        rows = db(db.wiki.page==page).select()
    else:
        rows = None
        page = ""
        
    if rows:
        form = SQLFORM(db.wiki, rows[0])
    else:
        form = SQLFORM(db.wiki)
        form.vars.page = page
        
    if form.accepts(request.vars, session):
        session.flash = "Page updated!"
        redirect(URL("view", args=request.args))

    return dict(form=form)
