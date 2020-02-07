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

    class CmpDotFiles(object):

        def __init__(self):
            pass
        
        def __call__(self, path):
            if ".git" in path or ".svn" in path or ".gitkeep" in path or ".gitignore" in path:
                return True
            else:
                return False



    @staticmethod
    def unlink(fname):
        try:
            rm = str("DEL %s" % fname)
            os.system(rm)
        except:
            pass

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
    def getListOfFiles(dirName, opt=None):
        # create a list of file and sub directories 
        # names in the given directory 
        listOfFile = os.listdir(dirName)
        allFiles = list()
        # Iterate over all the entries
        for entry in listOfFile:            
            #if opt is not None and opt(entry) is True:
            #    continue

            fullPath = os.path.join(dirName, entry)
                
            # If entry is a directory then get the list of files in this directory 
            if os.path.isdir(fullPath):
                allFiles = allFiles + Utils.getListOfFiles(fullPath, opt)
            else:
                if opt is not None and opt(fullPath) is False:
                    allFiles.append(fullPath)
                elif opt is None:
                    allFiles.append(fullPath)
                
        return allFiles


    @staticmethod 
    def deltadir(dirA, dirB):
        if dirA is None or dirB is None:
            return None
        
        direntA = Utils.getListOfFiles(dirA, Utils.CmpDotFiles())
        direntB = Utils.getListOfFiles(dirB, Utils.CmpDotFiles())        
        deltas = {}
        
        for j in range(0, len(direntB)):
            d1 = direntB[j].split(dirB)[-1]
            if d1 in deltas.keys():
                deltas[d1] += 1
            else:
                deltas[d1] = 1


        for i in range(0, len(direntA)):
            d1 = direntA[i].split(dirA)[-1]
            if d1 in deltas.keys():
                deltas[d1] += 1
            else:
                deltas[d1] = 1

        return deltas

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
                gpull = str("git pull")
                chkout = str("git checkout master")
                cmmsg = "Automatic ABM commit for a DB file"
                adddb = str("git add %s" % Utils.db.fname())
                cmtdb = str("git commit -m \"%s\"" % cmmsg)
                push = str("git push")
                Utils.sshel.execute(chkout)
                Utils.sshel.execute(gpull)
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

    
    @staticmethod
    def get_repo_type(repouri):
        rt = NS.RepoType()
        if repouri is not None:
            spl = repouri.lower().split("/")
            if len(spl) > 6:
                parseOffset = rt(spl[6])
        return parseOffset



if __name__ == "__main__":
    
    result = Utils.deltadir("D:\Dev\migrationtool\svnrepos\WhatsAppIm_1_1_0_WhatsAppIm", "D:\Dev\migrationtool\gitrepos\WhatsAppIm_1_1_0") 
    '''
    result = Utils.deltadir("D:\\Dev\\migrationtool\\svnrepos\\Infra_1_2_1_Infra", "D:\\Dev\\migrationtool\\gitrepos\\Infra_1_2_1")
    print "OK"
    '''