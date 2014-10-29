#!/usr/bin/env python
# coding:utf-8

"Database utilities API (sqlite3)"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2014 Mariano Reingart"
__license__ = "GPL 3.0"


import os
import sqlite3


class Database():
    "Simple database abstraction layer"
    
    def __init__(self, path, **kwargs):
        self.cnn = sqlite3.connect(path)
        self.primary_keys = {}
    
    def create(self, table, _auto=True, **fields):
        "Create a table in the database for the given name and fields dict"
        cur = self.cnn.cursor()
        sql = []
        sql.append("CREATE TABLE IF NOT EXISTS %s (" % table)
        for i, (field_name, field_type) in enumerate(fields.items()):
            sql_type = {int: "INTEGER", float: "REAL", str: "TEXT"}[field_type]
            if field_name == table + "_id":
                sql_constraint = "PRIMARY KEY"
                # store primary key for further reference
                self.primary_keys[field_name] = table
                if _auto:
                    sql_constraint += " AUTOINCREMENT"
            elif field_name.endswith("_id"):
                # add a foreign key:
                sql_constraint = "REFERENCES %s" % (
                    self.primary_keys[field_name])
            else:
                sql_constraint = ""
            sql.append (" %s %s %s" % (field_name, sql_type, sql_constraint))
            if i < len(fields) - 1:
                sql[-1] = sql[-1] + ","
        sql.append(");")
        sql = '\n'.join(sql)
        cur.execute(sql)

    def insert(self, table, **kwargs):
        "Insert a row for the given values in the specified table"
        items = kwargs.items()
        fields = ', '.join([k for k, v in items])
        placemarks = ', '.join(['?' for k, v in items])
        sql = "INSERT INTO %s (%s) VALUES (%s)" % (table, fields, placemarks)
        cur = self.cnn.cursor()
        cur.execute(sql, [v for k, v in items])
        self.cnn.commit()
        return cur.lastrowid

    def update(self, table, **kwargs):
        "Update rows using the given values (filter by primary key)"
        items = kwargs.items()
        pk = table + "_id"
        placemarks = ', '.join(["%s=?" % k for k, v in items if k != pk])
        values = [v for k, v in items if k != pk] + [kwargs[pk]]
        sql = "UPDATE %s SET %s WHERE %s = ?" % (table, placemarks, pk)
        cur = self.cnn.cursor()
        cur.execute(sql, values)
        self.cnn.commit()
        return cur.rowcount

    def delete(self, table, **kwargs):
        "Delete rows (filter by given values)"
        items = kwargs.items()
        placemarks = ' AND '.join(["%s=?" % k for k, v in items])
        values = [v for k, v in items]
        sql = "DELETE FROM %s WHERE %s" % (table, placemarks)
        cur = self.cnn.cursor()
        cur.execute(sql, values)
        self.cnn.commit()
        return cur.rowcount


if __name__ == "__main__":
    db = Database(path="test.db")
    db.create("t1", t1_id=int, f=float, s=str)
    db.create("t2", t2_id=int, f=float, s=str, t1_id=int)
    id1 = db.insert("t1", f=3.14159265359, s="pi")
    id2 = db.insert("t2", f=2.71828182846, s="e", t1_id=id1)
    ok = db.update("t1", t1_id=id1, s="PI")
    assert ok > 0
    ok = db.delete("t2", f=2.71828182846, s="e")
    assert ok > 0
