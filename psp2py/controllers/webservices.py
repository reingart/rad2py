from gluon.admin import *
from gluon.fileutils import abspath, read_file, write_file
from gluon.tools import Service
from glob import glob
import shutil
import platform
import time
import base64


service = Service(globals())

def requires_admin(action):
    "decorator that prevents access to action if not admin password"

    def f(*a, **b):

        basic = request.env.http_authorization
        if not basic or not basic[:6].lower() == 'basic ':
            raise HTTP(401,"Wrong credentials")
        (username, password) = base64.b64decode(basic[6:]).split(':')
        if not verify_password(password) or not is_manager():
            time.sleep(10)
            raise HTTP(403,"Not authorized")
        return action(*a, **b)

    f.__doc__ = action.__doc__
    f.__name__ = action.__name__
    f.__dict__.update(action.__dict__)
    return f



@service.jsonrpc
@requires_admin
def login():
    "dummy function to test credentials"
    return True


@service.jsonrpc
@requires_admin
def list_apps():
    "list installed applications"
    regex = re.compile('^\w+$')
    apps = [f for f in os.listdir(apath(r=request)) if regex.match(f)]
    return apps


@service.jsonrpc
@requires_admin
def list_apps():
    "list installed applications"
    regex = re.compile('^\w+$')
    apps = [f for f in os.listdir(apath(r=request)) if regex.match(f)]
    return apps

@service.jsonrpc
@requires_admin
def list_files(app):
    files = listdir(apath('%s/' % app, r=request), '.*\.py$')
    return [x.replace('\\','/') for x in files]

@service.jsonrpc
@requires_admin
def read_file(filename):
    """ Visualize object code """
    f = open(apath(filename, r=request), "rb")
    try:
        data = f.read().replace('\r','')
    finally:
        f.close()
    return data

@service.jsonrpc
@requires_admin
def write_file(filename, data):
    f = open(apath(filename, r=request), "wb")
    try:
        f.write(data.replace('\r\n', '\n').strip() + '\n')
    finally:
        f.close()


def call():
    session.forget()
    return service()

