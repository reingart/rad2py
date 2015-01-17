#!/usr/bin/env python
# coding:utf-8

"Database utilities API (sqlite3)"

__author__ = "Mariano Reingart (reingart@gmail.com)"
__copyright__ = "Copyright (C) 2014 Mariano Reingart"
__license__ = "GPL 3.0"


import os
import sqlite3
import UserDict


DEBUG = True
SQL_TYPE_MAP = {int: "INTEGER", float: "REAL", str: "TEXT", bool: "BOOLEAN"}


class Database():
    "Simple database abstraction layer"
    
    def __init__(self, path, **kwargs):
        self.cnn = sqlite3.connect(path)
        self.cnn.row_factory = sqlite3.Row
        self.primary_keys = {}
        self.cur = None
    
    def cursor(self, force=False):
        "Instantiate a new (if needed) cursor to execute SQL queries"
        if not self.cur or force:
            self.cur = self.cnn.cursor()
        return self.cur

    def commit(self):
        "Confirm any changes made to the database (if not closed)"
        if self.cnn:
            self.cnn.commit()

    def rollback(self):
        "Revert any changes made to the database (if not closed)"
        if self.cnn:
            self.cnn.rollback()

    def create(self, table, _auto=True, **fields):
        "Create a table in the database for the given name and fields dict"
        cur = self.cnn.cursor()
        sql = []
        sql.append("CREATE TABLE IF NOT EXISTS %s (" % table)
        for i, (field_name, field_type) in enumerate(fields.items()):
            sql_type = SQL_TYPE_MAP[field_type]
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
        if DEBUG: print sql, [v for k, v in items]
        cur.execute(sql, [v for k, v in items])
        return cur.lastrowid

    def update(self, table, **kwargs):
        "Update rows using the given values (filter by primary key)"
        items = kwargs.items()
        pk = table + "_id"
        placemarks = ', '.join(["%s=?" % k for k, v in items if k != pk])
        values = [v for k, v in items if k != pk] + [kwargs[pk]]
        sql = "UPDATE %s SET %s WHERE %s = ?" % (table, placemarks, pk)
        cur = self.cursor()
        if DEBUG: print sql, values
        cur.execute(sql, values)
        return cur.rowcount

    def delete(self, table, **kwargs):
        "Delete rows (filter by given values)"
        items = kwargs.items()
        placemarks = ' AND '.join(["%s=?" % k for k, v in items])
        values = [v for k, v in items]
        sql = "DELETE FROM %s WHERE %s" % (table, placemarks)
        cur = self.cursor()
        if DEBUG: print sql, values
        cur.execute(sql, values)
        return cur.rowcount

    def select(self, table, **kwargs):
        "Query rows (filter by given values)"
        items = kwargs.items()
        basic_types = tuple(SQL_TYPE_MAP.keys())
        aggregate_types = {sum: 'sum', len: 'count', min: 'min', max: 'max'}
        all_types = basic_types + tuple(aggregate_types.keys())
        where = ' AND '.join(["%s %s ?" % (k, "=" if v is not None else " is ") 
                              for k, v in items if v not in all_types])
        fields = ', '.join([(k if v in basic_types 
                               else "%s(%s)" % (aggregate_types[v], k))
                            for k, v in items 
                            if v in all_types]) or "*"
        if [v for k, v in items if v in aggregate_types]:
            group_by = ', '.join([k for k, v in items 
                                    if not v in (aggregate_types.keys())])
        else:
            group_by = None
        values = [v for k, v in items if v not in all_types]
        sql = "SELECT %s FROM %s" % (fields, table)
        if where:
            sql += " WHERE %s" % where
        if group_by and fields != "*":
            sql += " GROUP BY %s" % group_by
        cur = self.cursor()
        if DEBUG: print sql, values
        cur.execute(sql, values)
        return cur.fetchall()

    def __getitem__(self, table_name):
        "Return an intermediate accesor to the table (don't query the db yet)" 
        return Table(self, table_name)

    def __del__(self):
        if DEBUG: print "Delayed COMMIT!"
        self.commit()

    def close(self):
        "Clean up orderly"
        self.cnn.close()
        self.cnn = None


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

    def __call__(self, **kwargs):
        "Return an intermediate accesor to the record (using kwargs as filter)" 
        return Row(self.db, self.table_name, query=kwargs)
    
    def new(self, **kwargs):
        "Create an empty record to be inserted in the table"
        row = Row(self.db, self.table_name, {})
        row.update(kwargs)
        return row

    def append(self, data):
        "Short-cut to insert a row (data: fields values dict)"
        return self.db.insert(self.table_name, **data)
        
    def delete(self, **kwargs):
        "Short-cut to remove rows (filter: fields values dict)"
        return self.db.delete(self.table_name, **kwargs)

    def select(self, **kwargs):
        "Short-cut to return a list of select rows (filter: fields values dict)"
        for r in self.db.select(self.table_name, **kwargs):
            row = Row(self.db, self.table_name)
            row.load(r)
            yield row


class Row():
    "Dict-like to map stored fields in the database" 
    
    autocommit = True
    
    def __init__(self, db, table_name, primary_key=None, query=None):
        self.db = db
        self.table_name = table_name
        self.primary_key = primary_key or {}
        self.query = query or primary_key
        self.data_in = {}
        self.data_out = {}
    
    def load(self, data=None):
        "Fetch the record from the database"
        if not data:
            rows = self.db.select(self.table_name, **self.query)
        else:
            rows = [data]
        if rows:
            self.data_in = dict(rows[0])    # convert from sqlite custom dict
            if not self.primary_key:
                pk = self.table_name + "_id"
                self.primary_key = self.query = {pk: self.data_in.get(pk)}
    
    def save(self):
        "Write the modified values to the database"
        pk = self.table_name + "_id"
        if not self.data_out:
            # no modification, abort any SQL
            new_id = None
        elif self.primary_key:
            self.data_out.update(self.primary_key)
            self.db.update(self.table_name, **self.data_out)
            new_id = self.primary_key.values()[0]
        else:
            new_id = self.db.insert(self.table_name, **self.data_out)
            # store the new id so the record could be re-fetched on next access
            self.primary_key = self.query = {pk: new_id}
            self.data_in.update(self.primary_key)
        # assume data was written correctly and update internal cache:
        self.data_in.update(self.data_out)
        self.data_out = {}
        return new_id
    
    def erase(self):
        "Remove a record from the database"
        if self.primary_key:
            self.db.delete(self.table_name, **self.primary_key)
        else:
            # record not inserted yet!!!
            pass
    
    def keys(self):
        if not self.data_in and self.query:
            self.load()
        return self.data_in.keys() if self.data_in else self.data_out.keys()
    
    def update(self, other):
        # selective update: do not modify if value didn't changed
        for k, v in other.items():
            if not k in self.data_in or self.data_in[k] != v:
                self.data_out[k] = v

    def get(self, field, default=None):
        try:
            return self.__getitem__(field)
        except KeyError:
            return default
        
    def __getitem__(self, field):
        "Read the field value for this record"
        # return the most updated value (it could not had reached the db yet)
        # also avoid early unneeded insert/update (for example, for uuid fields) 
        if field in self.data_out:
            return self.data_out[field]            
        if not (self.primary_key or self.query):
            # not inserted yet, first save
            self.save()
        # real record should be in the database, fetch if necessary
        if field not in self.data_in:
            self.load()
        # return the value stored in the database
        return self.data_in[field]

    def __setitem__(self, field, value):
        "Store the field value for further update (at the destructor)"
        # load to get the record id
        if not self.primary_key and self.query:
            self.load()
        self.data_out[field] = value

    def __delitem__(self, field):
        "Remove the field from the internal cache"
        del self.data_in[field]
    
    def __del__(self):
        "Write data to the database on destruction"
        # Note that this could not be immediate!
        # Also, exceptions here could be ignored by Python!
        if self.data_out and self.autocommit:
            print "Autocommit!", self
            self.save()

    def __nonzero__(self):
        if not self.data_in:
            self.load()
        return bool(self.data_in)

    def __len__(self):
        if not self.data_in:
            self.load()
        return len(self.data_in)

    def __contains__(self, key):
        return key in self.data_in or key in self.data_out


class DictShelf(UserDict.DictMixin):
    "Database shelve replacement implementation (dictionary-like object)"
    
    def __init__(self, db, table_name, key_field_name, autocommit=True, 
                       **filters):
        self.db = db
        self.table_name = table_name
        self.key_field_name = key_field_name
        self.filters = filters
        self.deleted = []
        self.autocommit = autocommit
        self.query()
    
    def query(self):
        self.dict = {}
        # populate the internal dictionary:
        for r in self.db.select(self.table_name, **self.filters):
            row = Row(self.db, self.table_name)
            row.autocommit = self.autocommit
            row.load(r)
            self.dict[r[self.key_field_name]] = row

    def keys(self):
        return self.dict.keys()

    def __len__(self):
        return len(self.dict)

    def has_key(self, key):
        return key in self.dict

    def __contains__(self, key):
        return key in self.dict

    def get(self, key, default=None):
        if key in self.dict:
            return self.dict[key]
        return default

    def __getitem__(self, key):
        return self.dict[key]

    def __setitem__(self, key, value):
        # create a new Row proxy (value should be a dict!)
        if not isinstance(value, Row):
            row = Row(self.db, self.table_name)
            row.autocommit = self.autocommit
            value.update(self.filters)
            row.update(value)
        else:
            row = value
        row[self.key_field_name] = key
        self.dict[key] = row
        
    def setdefault(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            self[key] = default
            return self[key]

    def __delitem__(self, key):
        row = self.dict[key]
        self.deleted.append(row)
        del self.dict[key]

    def close(self):
        self.sync(self.autocommit)

    def __del__(self):
        self.close()

    def sync(self, commit=True):
        "Write back all the changes to the database" 
        if commit and self.dict is not None:
            for row in self.dict.values():
                row.save()
            for row in self.deleted:
                row.erase()
            self.deleted = []
            self.db.commit()
        elif self.dict is not None:
            # destroy internal dict to avoid commit later (TODO: requery)
            self.dict = None
            # revert any changes
            self.db.rollback()
            self.db.close()


class ListShelf(DictShelf):
    "Database shelve replacement implementation (list-like object)"
    
    # synchronization of changes in list position is done in the "key" field
    base = 1    # python is 0 based, database records are 1 based
    
    def insert(self, pos, value):
        # relocate the items 
        for i in range(len(self), pos, -1):
            self[i] = self[i - 1]
            # soft unlink (or next modification will update the item)
            del self.dict[i + self.base - 1]
        self[pos] = value
    
    def append(self, value):
        pos = len(self) 
        self[pos] = value

    def __setitem__(self, index, item):
        if isinstance(index, slice):
            if index.step is not None:
                raise NotImplementedError
            delete_indexes = []
            # store a list of items (one at a time)
            for j, i in enumerate(range(index.start, index.stop)):
                if j > len(item) - 1:
                    delete_indexes.append(i)
                else:
                    self[i] = item[j]
            # if the list is smaller, delete the rest of the items 
            for i in reversed(delete_indexes):
                del self[i]
            return
        # if there is a item already, do not create a new row (preserve pk)
        if (index + self.base) in self.dict:
            row = DictShelf.__getitem__(self, index + self.base)
            row.update(dict(item))
            item = row
        # store the item (calling the base class)
        return DictShelf.__setitem__(self, index + self.base, item)

    def __getitem__(self, index):
        if isinstance(index, slice):
            if index.step is not None:
                raise NotImplementedError
            ret = []
            # fetch a list of items (one at a time)
            for i in range(index.start, index.stop):
                ret.append(self[i])
            return ret
        else:
            # fetch an individual item
            return DictShelf.__getitem__(self, index + self.base)

    def __delitem__(self, index):
        if isinstance(index, slice):
            if index.step is not None:
                raise NotImplementedError
            # remove one by one
            for i in range(index.stop - 1, index.start - 1, -1):
                del self[i]
        else:
            max_index = len(self) - 1
            # delete the item in the database
            DictShelf.__delitem__(self, index + self.base)
            # relocate elements
            for i in range(index, max_index):
                self[i] = self[i + 1]
                # soft unlink as moved (do not delete on the database):
                del self.dict[i + 1 + self.base]

    def __iter__(self):
        "Iterate values in list order"
        for i in sorted(self.dict.keys()):
            yield self.dict[i]

    def keys(self):
        "Returns the correct keys (index) for compatibility with dict-like uses"
        for k in self.dict.keys():
            yield k - self.base


if __name__ == "__main__":
    db = Database(path="test.db")
    t1 = db.create("t1", t1_id=int, f=float, s=str)
    db.create("t2", t2_id=int, f=float, s=str, n=int, t1_id=int)
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
    r = db['t1'].new(f=0, s='hola')
    t1_id = r.save()
    print t1_id
    assert r['t1_id'] == t1_id
    db['t1'][t1_id]['f'] +=1
    db['t1'][t1_id]['f'] +=1
    assert db['t1'][t1_id]['f'] == 2 
    assert not db['t1'][t1_id+1]        # this record doesn't exist
    assert db['t1'](t1_id=t1_id)['f'] == 2
    r['f'] = 99
    r = db['t1'](f=99)
    print r['t1_id']
    r['f'] = 98
    print r['t1_id']
    r.save()
    # test shelve replacement (dict of dict):
    s = DictShelf(db, "t2", "s", t1_id=id1)
    s['hola'] = {'n': 1, 'f': 3.14}
    s['chau'] = {'n': 2}
    s['hola']['n'] = 3
    s.setdefault('nana', {})['n'] = 4
    s.close()
    s = DictShelf(db, "t2", "s", t1_id=id1)
    assert s['hola']['n'] == 3
    assert s['hola']['t1_id'] == id1
    assert s['chau']['n'] == 2
    assert s['chau']['t1_id'] == id1
    assert s['nana']['n'] == 4
    s['hola']['n'] = 1
    s['nana']['n'] = 3
    s.close()
    print "Closed!"
    
    # test shelve replacement (list of dict):
    l = ListShelf(db, "t2", "n", t1_id=id1)
    assert l[0]['s'] == 'hola'
    assert l[1]['s'] == 'chau'
    l.insert(2, {'s': 'lola', 'f': 8.50})
    assert l[3]['s'] == 'nana'
    del l[0]
    assert l[0]['s'] == 'chau'
    assert l[1]['s'] == 'lola'
    del l[0:2]
    assert l[0]['s'] == 'nana'
    l[0]['s'] = 'prueba'
    t2_id = l[0]['t2_id']
    l[0] = {'s': 'nada'}
    assert t2_id == l[0]['t2_id']
    s.close()

