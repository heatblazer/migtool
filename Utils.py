from db import dbutil as DB
from Globals import * 
from Globals import NS
from Shell import Cmd
import os
import subprocess 
import sys
import warnings

class Utils(object):
    """ Utulity functions - static class """
    dmpfile = None # fptr
    sshel = Cmd()
    sresult = None
    memdmp = list()
    db = DB()
    @staticmethod 
    def rmdir(dir_path):
        try:
            fcmd = str("rmdir /Q /S %s" % dir_path)
            os.system(fcmd)
        except :
            Utils.printwf(str("ERROR: %s does not exists"))
            pass


    @staticmethod
    def printcwd():
        ret = os.getcwd()
        Utils.printwf(str("CWD: [%s]" % str(ret)))
        return ret


    @staticmethod
    def home_dir():
        return os.path.dirname(os.path.realpath(__file__))


    @staticmethod
    def home():
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        return os.path.dirname(os.path.realpath(__file__))


    @staticmethod
    def dump(data):
        """dump to memory or file"""
        if Utils.memdmp is None:
            Utils.memdmp = list()
        if NS.LOG_DISABLED is True:
            Utils.memdmp.append(data)
        if Utils.dmpfile is None and NS.LOG_DISABLED is False:
            Utils.dmpfile = open(r"C:\\ProgramData\\Dmp.txt", "w")    
        if NS.LOG_DISABLED is False:
            Utils.dmpfile.write(str(data))


    @staticmethod
    def finalize():
        Utils.home()
        if Utils.db.save() is not True:
            Utils.printwf("ERROR: Failed to save db file")
        else:
            if NS.SVNGIT_ON_ABM:
                Utils.printwf("Will commit db.json to the master repo")
                chkout = str("git checkout master")
                cmmsg = "Automatic ABM commit for a DB file"
                adddb = str("git add %s" % Utils.db.fname())
                cmtdb = str("git commit -m \"%s\"" % cmmsg)
                push = str("git push")
                Utils.sshel.execute(chkout)
                Utils.sshel.execute(adddb)
                Utils.sshel.execute(cmtdb)
                Utils.sshel.execute(push)

        for i in Utils.memdmp:
            Utils.printwf(i)
        
        if Utils.dmpfile is not None:
            Utils.dmpfile.close()
        Utils.sshel.kill()


    @staticmethod
    def mkdir(dir_name):
        sshel = Cmd()
        dn = str("mkdir %s" % dir_name)
        sshel.execute(dn, True)


    @staticmethod
    def xcopy(src, dst):
        xc = str("xcopy /E /I %s %s /Y" % (src, dst))
        sshel = Cmd()
        sshel.execute(xc)
        if len(sshel.std_err()) == 0:
            return True
        else:
            return False


    @staticmethod
    def probe_dirs(dirs):
        res = True
        for d in dirs:
            if os.path.isdir(d):
                res &=  len(os.listdir(d)) > 1
            else:
                res &= False        
        return res


    @staticmethod
    def dir_exists_ex(path, wdata=True):
        """wdata: mark False if only check for pathname, or default for path w contents"""
        res = False
        if os.path.isdir(path):
            if wdata is True:              
                res = len(os.listdir(path)) > 1
            res = True
        return res


    @staticmethod
    def git_clrf(opt="false"):
        sshel = Cmd()
        cl = str("git config --global core.safecrlf %s" % opt)
        sshel.execute(cl)


    @staticmethod
    def load_svngit(fname):
        try:
            fp = open(fname, 'r')
            lines = fp.readlines()
            for line in lines:
                line = line.replace('\r', '').replace('\n', '')
                spl = line.split(',')
                if len(spl) == 3:
                    NS.GSvnGitMeta.append({"branch":spl[2], "svn":spl[0], "git":spl[1]})
                elif len(spl) > 3:
                    tags = spl[3:]
                    NS.GSvnGitMeta.append({"branch":spl[2], "svn":spl[0], "git":spl[1], "tags":tags})
            fp.close()
            return True
        except:
            Utils.printwf(str("Could not read file: (%s)" % fname))
            return False


    @staticmethod
    def get_search():
        tmp = str(Utils.sresult)
        Utils.sresult = None
        return tmp

    @staticmethod
    def printwf(data):
        """print stdout and stderr and flush the fdescriptors"""
        print data
        sys.stdout.flush()
        sys.stderr.flush()

    @staticmethod
    def find_file(dir, match):
        listOfFile = os.listdir(dir)
        allfiles = list()
        for entry in listOfFile:
            fullpath = os.path.join(dir, entry)
            if entry == match:
                Utils.sresult = fullpath
            if os.path.isdir(fullpath):
                allfiles = allfiles + Utils.find_file(fullpath, match)
            else:
                allfiles.append(fullpath)
        return allfiles