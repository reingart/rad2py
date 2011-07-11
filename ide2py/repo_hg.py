#!/usr/bin/env python
# coding:utf-8

"Integration of mercurial hg version control repository"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2011 Mariano Reingart"
__license__ = "GPL 3.0"

import os
import wx
import wx.html

from mercurial import ui, hg, cmdutil

# based on web2py mercurial support

class MercurialRepo(object):

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
            open(hgignore, 'w').write(self._hgignore_content)
        self.repo = repo

    def commit(self, comment):
        oldid = self.repo[self.repo.lookup('.')]
        cmdutil.addremove(self.repo)
        self.repo.commit(text=comment)
        if self.repo[self.repo.lookup('.')] == oldid:
            return 'no changes'
        return "ok"

    def status(self):
        for file in self.repo[self.repo.lookup('.')].files():
            print "file"
        
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


if __name__ == '__main__':

    repo = MercurialRepo("C:/rad2py")
    repo.status()
    