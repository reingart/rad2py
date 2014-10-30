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
        self.cnn.row_factory = sqlite3.Row
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

    def select(self, table, **kwargs):
        "Query rows (filter by given values)"
        items = kwargs.items()
        basic_types = int, str, float
        aggregate_types = {sum: 'sum', len: 'count', min: 'min', max: 'max'}
        all_types = basic_types + tuple(aggregate_types.keys())
        where = ' AND '.join(["%s=?" % k for k, v in items
                                         if v not in all_types])
        fields = ', '.join([(k if v in basic_types 
                               else "%s(%s)" % (aggregate_types[v], k))
                            for k, v in items 
                            if v in all_types]) or "*"
        group_by = ', '.join([k for k, v in items 
                                if not v in (aggregate_types.keys())])
        values = [v for k, v in items if v not in all_types]
        sql = "SELECT %s FROM %s" % (fields, table)
        if where:
            sql += " WHERE %s" % where
        if group_by:
            sql += " GROUP BY %s" % group_by
        cur = self.cnn.cursor()
        print sql, values
        cur.execute(sql, values)
        self.cnn.commit()
        return cur.fetchall()

    def __getitem__(self, table_name):
        "Return an intermediate accesor to the table (don't query the db yet)" 
        return Table(self, table_name)


class Table():
    "Dict/List-like to map records in a database"

    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name

    def __setitem__(self, key, data):
        "Short-cut to update a row (key: pk, data: fields values)"
        data[self.table_name + "_id"] = key
        self.db.update(self.table_name, **data)

    def __getitem__(self, key):
        "Return an intermediate accesor to the record (don't query the db yet)" 
        return Row(self.db, self.table_name, {self.table_name + "_id": key})

    def append(self, data):
        "Short-cut to insert a row (data: fields values)"
        return self.db.insert(self.table_name, **data)


class Row():
    "Dict-like to map stored fields in the database" 
    
    def __init__(self, db, table_name, primary_key):
        self.db = db
        self.table_name = table_name
        self.primary_key = primary_key
        self.data_in = {}
        self.data_out = {}
    
    def load(self):
        "Fetch the record from the database"
        rows = self.db.select(self.table_name, **self.primary_key)
        if rows:
            self.data_in = rows[0]
    
    def save(self):
        "Write the modified values to the database"
        self.data_out.update(self.primary_key)
        self.db.update(self.table_name, **self.data_out)
    
    def __getitem__(self, field):
        "Read the field value for this record"
        if not self.data_in:
            self.load()
        return self.data_in[field]

    def __setitem__(self, field, value):
        "Store the field value for further update (at the destructor)"
        self.data_out[field] = value
    
    def __del__(self):
        "Write data to the database on destruction"
        # Note that this could not be immediate!
        # Also, exceptions here could be ignored by Python!
        if self.data_out:
            self.save()

    def __nonzero__(self):
        if not self.data_in:
            self.load()
        return bool(self.data_in)

    def __len__(self):
        if not self.data_in:
            self.load()
        return len(self.data_in)
        

if __name__ == "__main__":
    db = Database(path="test.db")
    t1 = db.create("t1", t1_id=int, f=float, s=str)
    db.create("t2", t2_id=int, f=float, s=str, t1_id=int)
    id1 = db.insert("t1", f=3.14159265359, s="pi")
    id1 = db.insert("t1", f=2.71828182846, s="e")
    id2 = db.insert("t2", f=2.71828182846, s="e", t1_id=id1)
    ok = db.update("t1", t1_id=id1, s="PI")
    assert ok > 0
    ok = db.delete("t2", f=2.71828182846, s="e")
    assert ok > 0

    rows = db.select('t1', f=sum, s="pi")
    print rows[0]["sum(f)"]
    
    # dict-like syntax (inspired by shelve):
    r = {'f': 0, 's': 'hola'}
    t1_id = db['t1'].append(r)
    db['t1'][t1_id]['f'] +=1
    db['t1'][t1_id]['f'] +=1
    assert db['t1'][t1_id]['f'] == 2 
    assert not db['t1'][t1_id+1]        # this record doesn't exist

