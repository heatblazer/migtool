import xml.etree.ElementTree as ET
from Utils import Utils
from threading import Thread
from threading import Lock as mtx
from time import sleep

#Helpers 
class Helpers(object):
    """helper stuff"""

    @staticmethod 
    def is_validchash(s):
        bfail = True
        for c in s:
            if (c.lower() >= 'a'and c.lower() <= 'f') or (c >= '0' and  c <= '9'):
                pass
            else:
                bfail &= False
        return bfail


    @staticmethod 
    def match_abm_aligned(data):
        if data.lower().find("abm") is not -1 and data.find("Automatic ABM commit") is not -1:
            if data.lower().find("increase component version to") is not -1:
                return True
            else: 
                return False
        else:
            return False
    

    @staticmethod 
    def match_abm(data):
        if data.lower().find("abm") is not -1 and data.find("Automatic ABM commit") is not -1:
            return True
        else:
            return False

    @staticmethod
    def match_abmasmanual(data):
        if data.lower().find("abm") is not -1 and data.find("Automatic ABM commit") is -1:
            return True
        else:
            return False


    @staticmethod
    def hwm(dic):
        """high watermark algo"""
        h = 0
        for key in dic:
            if key > h:
                h = key
        return h
    


#Functors
class Functor(object):
    """abstract function object class to be derived by a real callable obj"""
    def __init__(self):
        pass


    def __call__(self):
        self.do_work()


    def do_work(self):
        """override this"""
        raise BaseException()
    


class PThread(Thread):

    def __init__(self, name="DefaultRunner", userData=None, fn=None):
        Thread.__init__(self)
        self._name = name
        self._udata = userData
        self._lock = mtx()
        self._fn = fn

    def run(self):
        if self._fn is not None:
            self._fn()
                


#Xml Update ctx class
class XmlUpdateContext(object):
    """ store ComponentsVersion.xml context here and update it"""
    def __init__(self, xmlfile):
        self._bakfile = str("%s.bak" % xmlfile)
        self._lookup = {}
        self._xmltree = ET.parse(xmlfile)
        self._root = self._xmltree.getroot()
        for child in self._root:
            if child.attrib['Name'].startswith('_'):
                fix = child.attrib['Name'].replace('_', '')
                self._lookup[fix] = child
            else:
                self._lookup[child.attrib['Name']] = child
        self.version = None
        self.Name = None


    def stringify_namever(self):
        return str("%s_%s" % (self.Name, self.version))


    def set_vername(self, ver, name):
        self.version = ver
        self.Name = name


    def get_vername(self):
        return (self.version, self.Name)

    def get_attrib_by_name(self, name):
        if name in self._lookup:
            return self._lookup[name]
        return None

    def update(self, name, commithash):
        try:
            if commithash is not None and name is not None:
                self._lookup[name].set('CommitHash', commithash)
        except:
            pass # do something later: TODO!!!


    def finalize(self):
        if self._xmltree is not None:
            Utils.home()
            self._xmltree.write("%s" % self._bakfile)
