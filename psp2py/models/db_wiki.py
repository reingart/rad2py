# coding: utf8

db.define_table("wiki",
    Field("page", requires=IS_NOT_EMPTY()),
    Field("title", requires=IS_NOT_EMPTY()),
    Field("text", "text", 
        requires=IS_NOT_EMPTY(),
        comment=XML(A(str(T('MARKMIN format')),_href='http://web2py.com/examples/static/markmin.html')),
        ),
)
