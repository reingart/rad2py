#!/usr/bin/env python
# coding:utf-8

"Integration of mercurial hg version control repository"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

import os

from mercurial import ui, hg, cmdutil

# based on web2py mercurial support

_hgignore_content = """\
syntax: glob
*~
*.pyc
*.pyo
*.bak
cache/*
databases/*
sessions/*
errors/*
"""


class MercurialRepo(object):

    def __init__(self, path):
        uio = ui.ui()
        uio.quiet = True
        if not os.environ.get('HGUSER') and not uio.config("ui", "username"):
            os.environ['HGUSER'] = 'web2py@localhost'
        try:
            repo = hg.repository(ui=uio, path=path)
        except:
            repo = hg.repository(ui=uio, path=path, create=True)
        hgignore = os.path.join(path, '.hgignore')
        if not os.path.exists(hgignore):
            open(hgignore, 'w').write(_hgignore_content)
        self.repo = repo
        self.decode = None

    def commit(self, filepaths, message):
        oldid = self.repo[self.repo.lookup('.')]
        user = date = None
        match = cmdutil.match(self.repo, filepaths)
        node = self.repo.commit(message, user, date, match)
        if self.repo[self.repo.lookup('.')] == oldid:
            return None # no changes
        return True # sucess

    def cat(self, file1, rev=None):
        ctx = cmdutil.revsingle(self.repo, rev)
        m = cmdutil.match(self.repo, (file1,))
        for abs in ctx.walk(m):
            data = ctx[abs].data()
            if self.decode:
                data = self.repo.wwritedata(abs, data)
            return data

    def history(self):
        for file in self.repo[self.repo.lookup('.')].files():
            print file
        
        for change in self.repo.changelog:
            ctx=self.repo.changectx(change)
            revision, description = ctx.rev(), ctx.description()
            print revision, description

    def revert(self, revision):
        ctx=self.repo.changectx(revision)
        hg.update(self.repo, revision)
        print "reverted to revision %s" % ctx.rev()
    #    redirect(URL('default','design',args=app))
    #    return dict(
    #        files=ctx.files(),
    #        rev=str(ctx.rev()),
    #        desc=ctx.description(),
    #        form=form
    #        )

    def status(self, path=None):
        "show changed files in the working directory"

        revs = None
        node1, node2 = cmdutil.revpair(self.repo, revs)

        cwd = (path and self.repo.getcwd()) or ''
        copy = {}
        states = 'modified added removed deleted unknown ignored clean'.split()
        show = states

        stat = self.repo.status(node1, node2, cmdutil.match(self.repo, path),
                    'ignored' in show, 'clean' in show, 'unknown' in show,
                    )
        changestates = zip(states, 'MAR!?IC', stat)

        for state, char, files in changestates:
            for f in files:
                yield f, state
                #repo.wjoin(abs), self.repo.pathto(f, cwd)

    def rollback(self, dry_run=None):
        "Undo the last transaction (dangerous): commit, import, pull, push, ..."
        return self.repo.rollback(dry_run)

if __name__ == '__main__':

    r = MercurialRepo("..")
    for st, fn in r.status():
        print st, fn
    print r.cat("hola.py", rev=False)

    if raw_input("commit?"):
        import pdb; pdb.set_trace()
        ret = r.commit(["hola.py"], "test commit!")
        print "result", ret



