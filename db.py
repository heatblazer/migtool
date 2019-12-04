import json

class dbutil(object):

    def __init__(self):
        """init db and load it"""
        self._db = None
        self._fname = None


    def __del__(self):
        pass


    def load(self, fname):
        self._fname = fname
        try:
            with open(fname, 'r') as fp:
                self._db = json.load(fp)    
                fp.close()
                return True
        except:
            return False
        pass

    
    def printme(self):
        if self._db is not None:
            for record in self._db:
                print str("%s:%s" % (record, self._db[record]))


    def add_record(self, name):
        if self._db is not None:
            if name not in self._db:
                self._db[name] = {'tags':[], 'svnrev':0}


    def add_svnrev(self, rec, rev):
        if self._db is not None:
            if rec in self._db:
                self._db[rec]['svnrev'] = rev


    def get_svnrev(self, rec):
        if self._db is not None:
            if rec in self._db:
                return int(self._db[rec]['svnrev'])
            else:
                return -1


    def get_tags(self, rec):
        if self._db is not None:
            if rec in self._db:
                return self._db[rec]['tags']


    def clear_tags(self, rec):
        if self._db is not None:
            if rec in self._db:
                del(self._db[rec]['tags'])
                self._db[rec]['tags'] = None
                self._db[rec]['tags'] = []


    def add_tag(self, rec, tag):
        if self._db is not None:
            if rec in self._db:
                self._db[rec]['tags'].append(tag)


    def save(self):
        try:
            with open(self._fname, 'w') as fp:
                json.dump(self._db, fp, skipkeys=False, ensure_ascii=True, check_circular=True,allow_nan=True, cls=None, indent=2, separators=None,encoding='utf-8', default=None, sort_keys=False)
                fp.close()
                return True
        except:
            return False
        pass


    def fname(self):
        return self._fname

if __name__ == "__main__":
    #unit test
    r'''
    db = dbutil()
    db.load('db.json')
    db.add_record('Infra')
    db.add_record('Sau')
    db.add_svnrev('Infra', 99999)
    db.add_svnrev('Sau', 88888)
    for i in range(1, 10):
        db.add_tag('Sau', i)
        db.add_tag('Infra', i)

    db.printme()
    db.savedb()
    '''
    pass