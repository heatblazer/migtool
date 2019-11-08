r'''
Created 30.07.2019
@author izapryanov

-requirements:
    python2.7
    svn
    git
    bfg : https://confluence.atlassian.com/bitbucket/use-bfg-to-migrate-a-repo-to-git-lfs-834233484.html
    java jre
-command line example:

sgutil.py --dotag --file <file.txt>

NOTE: no longer needs the make.bat file to clone and build the platforms. Parsing the file with format:
http://svnrepo ,repouri/repo.git, branch

'''
import datetime
from db import dbutil as DataBaze
import json
import threading #for future use - pass SvnGitMixin to separate threads
import time
from time import sleep
import os
import subprocess 
import sys
import xml.etree.ElementTree as ET
import warnings

#Globals and constants
############################################################################
TEST_GIT_REPO_NAME = None #"TST4" #"TODO_MIGRATE"

GDEBUG = False

OK = 0

ERROR = 1

NO_CONNECTION_TO_SVN = 2

NO_CONNECTION_TO_GIT = 3

ERROR_INSUFFICIENT_CLONE_DEPTH = 4

REPO_BACKUP = "backup"

GUserMails = None

GMissingMails = {}

GSvnGitMeta = []

GSwitchCase = {}

SVNGIT_UPDATE_DB_ONLY = False

SVNGIT_ON_ABM = False

GDepth = 20

CMD_VERBOSE_MODE_ON = True

CSI_GIT_URI = "secret"

SVN_TEMP_DIR = "svnrepos"

GIT_TEMP_DIR = "gitrepos"

ABM_TEMP = "abmtemp"

LOG_DISABLED = True

GTHREAD_COUNT = 5 #test

FIX_DIRTY_TAGS = False

FIX_DIRTY_TAGS_SPECIAL = False

HELP_MESSAGE = """

Usage:\r\n
For bfg mode to perform a cleanup use: sgutil.py --dobfg --file <file>\r\n

For merge export svn to git use: sgutil.py --export --file <file>\r\n

For tagging use: sgutil.py --file <file> --tag\r\n

For untagging use: sgutil.py --file <file> --untag\r\n

For dump log use: sgutil.py --file <file> --dump-all\r\n

For complete merge repo and tag use: sgutil.py --file <file> --fullmerge\r\n

For specific removal of tags use: sgutil.py --file <file> --purge-tags\r\n

For other options view the sgutil.py file with your editor of choice :")\r\n

For updating a db file use: sgutil.py --update-db\r\n

For hinting you are on a build machine use: sgutil.py --abm\r\n

Usage for updateing ComponentsVersion.xml:
-cv0 <filename.xml> ... -cv<Filename.xml>

"""

ExcludedFilesForGitV1 = """
7z,arj,deb,pkg,rar,rpm,tar,
gz,tar.gz,z,ace,whl,gzip,zip,
bin,dmg,iso,toast,vcd,dat,db,apk,
exe,jar,war,ear,cab,dll,obj,dmp,
xlsx,docx,doc,ppt,pptm,pptx,
pdf,msi,msu,m_s_i,wsi,png,
jpg,jpeg,gif,ico
"""

ExcludedFilesForGitV2 = """
.cache,.chm,.dll,.exe,
.exp,.idb,.jpg,.lib,.Lib,
.ncb,.pcap,.pdf,.pk,.raw,
.obj,.pdb,.sdf,.suo,
.d,.Config.proj.bak,
.docx,.xlsx,.snoop,.AIT,
.o,.so,.out,.metadata
"""


############################################################################


#spawn a command
class Cmd(object):
    """ spawn a new process and capture stdout and stderr"""

    def __init__(self, verbose=False):
        self._out = None
        self._err = None
        self._dataout = []
        self._dataerr = []
        self.pro = None
        self._vmode = verbose


    def std_out(self):
        if self._out is not None:
            return self._out
        else:
            return None


    def std_out_data(self):
        return self._dataout


    def std_err(self):
        if self._err is not None:
            return self._err
        else:
            return None


    def flush(self):
        self._out = None
        self._dataout = None
        self._err = None 


    def execute(self, cmd, term=False):
        cmd.strip()
        if self._vmode is True:
            term = True
        fp = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=term)
        self.pro = fp
        (self._out, self._err) = fp.communicate()
        return len(self._err) == 0


    def terminate(self):
        if self.pro is not None:
            self.pro.terminate()
        self.pro = None


    def kill(self):
        if self.pro is not None:
            self.pro.kill()
        self.pro = None


    def execute_ex(self, cmd):
        cmd.strip()
        fp = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        while True:
            line = fp.stdout.readline()
            if not line:
                break
            else:
                self._dataout.append(line)                        
        pass


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

class Utils(object):
    """ Utulity functions - static class """
    dmpfile = None # fptr
    sshel = Cmd()
    sresult = None
    memdmp = list()
    db = DataBaze()
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
        if LOG_DISABLED is True:
            Utils.memdmp.append(data)
        if Utils.dmpfile is None and LOG_DISABLED is False:
            Utils.dmpfile = open(r"C:\\ProgramData\\Dmp.txt", "w")    
        if LOG_DISABLED is False:
            Utils.dmpfile.write(str(data))


    @staticmethod
    def finalize():
        Utils.home()
        Utils.db.printme()
        if Utils.db.save() is not True:
            Utils.printwf("Failed to save db file")
        else:
            if SVNGIT_ON_ABM:
                Utils.printwf("Will commit db.json to the master repo")
                cmmsg = "Automatic ABM commit for a DB file"
                cmd = Cmd()
                adddb = str("git add %s" % Utils.db.fname())
                cmtdb = str("git commit -m \"%s\"" % cmmsg)
                push = str("git push")
                cmd.execute(adddb)
                cmd.execute(cmtdb)
                cmd.execute(push)

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
                    GSvnGitMeta.append({"branch":spl[2], "svn":spl[0], "git":spl[1]})
                elif len(spl) > 3:
                    tags = spl[3:]
                    GSvnGitMeta.append({"branch":spl[2], "svn":spl[0], "git":spl[1], "tags":tags})
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
            self._xmltree.write("%s" % self._bakfile)

#TODO: implement that in the main(...) so it can be passed as arg... 

class Functor(object):
    """abstract function object class to be derived by a real callable obj"""
    def __init__(self, data):
        self._data = data #user data


    def __call__(self):
        self.do_work()


    def do_work(self):
        """override this"""
        raise BaseException()


class MergeRepos(Functor):
    """example merge repos functor"""
    def __init__(self, data):
        super(MergeRepos, self).__init__(data)
        

    def do_work(self):
        self._data.do_merge("{2019-01-01}", cleanup=clean)
    


#begin region SvnGitMixin
class SvnGitMixin(object):
    """ svn migrate to git, it clones repos, then checkoust them and copy/paste files from svn to git before commit/push them"""

    class versionh_t(object):
        """internal helper data class to store meaningful data from Version header file """
        #static cnt
        def __init__(self, major, minor, branch, fix, minfix):
            self.majorv = major
            self.minorv = minor
            self.branchv = branch
            self.fixv = fix
            self.minfixv = minfix

        def to_tag(self):
            return str("%s_%s_%s_%s_%s" %(self.majorv, self.minorv, self.branchv, self.minfixv, self.fixv))


    def __init__(self, svnuri=None, gituri=None, svnpath=None, gitpath=None, opt_tags=None):
        """ svn url, git url (both optional, git for bfg command is required), svn directory and git directory - required """
        self._gituri = gituri
        self._svnuri = svnuri
        self._metasvn = {}
        self._metagit = {}
        self._gitpath = gitpath
        self._svnpath = svnpath
        self._missing = list()
        self._isrunning = True
        self._hkgit = 0 #highest git ver
        self._hksvn = 0 #highest svn ver
        self._isInit = False
        self._repos = []       
        self._currentPID = None
        self._currentBranch = None
        self._shell = Cmd()
        self.sresult = None
        self._xmlContext = None
        self._git_forward_err = False
        self._tags = opt_tags # buffer all tags here
        pass #debg
    

    def __del__(self):
        """RAII"""
        self.terminate()
        self.end()


    def _set_path(self, path):
        res = True
        try:
            os.chdir(path)
        except:
            res = False
        return res
    

    def append_db(self, key, val):
        """unused"""
        pass
 

    def write_db(self):
        """ dump a json"""
        fname = str("%s\\out.json" % Utils.home_dir())
        with open(fname, 'w') as outfile:
            json.dump(self._db, outfile)


    def gitlog(self, optargs=" ", addall=False):
        """ wrapper of git log"""

        def _add_to_dic(key, data):
            if key not in self._metagit:
                self._metagit[key] = list()
                self._metagit[key].append(data)
            else:
                self._metagit[key].append(data) 


        def extract_rev(s):
            ret = -1
            if s.find("git-svn") is not -1:
                ns = s.replace('\n','').replace('\r', '')
                rev = ns[ns.index("git-svn-id:"): ]
                ret = int(rev[rev.find('@')+1:].split()[0])
            elif s.find("svn-revision:") is not -1:
                ns = s.replace('\n','').replace('\r', '')
                rev = ns[ns.index("svn-revision:"):]
                rev.replace('\r', '').replace('\n', '')
                ret = int(rev[rev.index(":")+1:])
            else:
                pass
            return ret


        def fix_broken_split(array, delimiter, sig=5):
            iter = 0 #count array and save state to prev
            for elem in array:
                if len(elem) >= sig:
                    test = elem.split('\n')
                    test[0].replace('\r', '').replace('\n', '')
                    ishex = Helpers.is_validchash(test[0])
                    if not ishex:
                        array[iter-1] = str("%s %s %s" % (array[iter-1], delimiter, elem))
                        spl.pop(iter)
                        pass
                    pass
                iter += 1
            return array # return a fixed array probably 


        self._set_path(self._gitpath)
        pull = str("git pull")
        glog = str("git log %s " % (optargs))
        self._shell.execute(pull)
        self._shell.execute(glog)
        omitnext = False
        spl = self._shell.std_out().split("commit ")
        spl = fix_broken_split(spl, "commit ")
        res = False
        errFreq = 0
        if len(spl) > 0:
            res = True
        for s in spl:
            errFreq += 1
            if len(s) == 0:
                continue

            if s.find("Merge pull request") is not -1:
                if errFreq == 1:
                    self._git_forward_err = True
                Utils.printwf(str(s))
                omitnext = True

            if omitnext is True:
                omitnext = False
                continue
            rrev = extract_rev(s)
            if rrev != -1:
                _add_to_dic(rrev, s)
            else:
                if errFreq == 1:
                    self._git_forward_err = True

        return res


    def svnlog(self, frm, to=str("HEAD")):
        """ wrapper to svn log """
        self._set_path(self._svnpath)
        svnupdate = str("svn up")    
        svnlog = str("svn log -r %s:%s" % (frm, to))
        self._shell.execute(svnupdate)
        self._shell.execute(svnlog)
        spl = self._shell.std_out().split("------------------------------------------------------------------------")
        for s in spl:
            s = s.lstrip("\r\n")
            s = s.rstrip("\r\n")
            if len(s) != 0:
                sspl = s.split()
                k = sspl[0]
                if k[1:] not in self._metasvn:
                    kk = int(k[1:])
                    self._metasvn.update({kk:s})


    def gitpop(self, commithash):
        """WARNING! Careful now when using that call : pops latest commit and resets to the prev in repo"""
        resettop = str("git reset --hard %s" % commithash)
        pushf = str("git push --force")
        self._shell.execute(resettop)
        self._shell.execute(pushf)
        pass # breakpnt


    def hwm(self, dic):
        h = 0
        for key in dic:
            if key > h:
                h = key
        return h
    

    def set_current(self, repo):
        self._repo = repo


    def init_branch(self, postfix, deleted=False):
        c = self._shell
        ret = str()
        os.chdir(self._gitpath) # go to dir path
        spl = self._gitpath.split('\\')
        origin = spl[len(spl)-1]
        repo = str("%s_%s" % (origin, postfix))
        self._repos.append(repo)
        ret = str(repo)
        try:               
            checkout = str("git checkout %s" % repo)
            push = str("git push --set-upstream origin %s" % repo)
            newbranch = str("git branch %s" % repo)            
            check = str("git branch -a")
            c.execute(check)
            if repo in c.std_out() and deleted is False:
                return ret
            elif repo in c.std_out() and deleted is True:
                chtoorgin = str("git checkout %s" % origin)
                deletebranch = str("git branch -D %s" % repo) # use upper D to be 'sure'
                deleteorigin = str("git push origin --delete %s" % repo)
                c.execute(chtoorgin)
                c.execute(deletebranch)
                c.execute(deleteorigin)               
                os.chdir(self._svnpath)
                return None
            else:
                c.execute(newbranch)
                c.execute(checkout)
                c.execute(push)
            return ret                
        except:
            os.chdir(self._svnpath)
            return None
    

    def add_and_commit(self, author, mail, date, msg, upstream):
        """ add and commit and push with specific author, mail, cmt message and to upstream repo"""
        gadd = str("git add .")
        gcmt = str("git commit --author=\"%s <%s>\" -m \"%s\" --date=%s" % (author, mail, msg, date))
        Utils.dump(str("INFO:%s" % gcmt))
        if TEST_GIT_REPO_NAME is not None:
            gpush = str("git push --set-upstream origin %s" % upstream)
        else:
            gpush = str("git push")
        c = self._shell
        self._currentPID = c
        c.execute(gadd)
        c.execute(gcmt)
        c.execute(gpush)
        

    def clone_bare(self, gituri, repo, branch=None):
        pydir = str(os.path.dirname(os.path.realpath(__file__)))       
        try:
            os.chdir(pydir)
        except:
            return False        
        repo = repo.replace('\n', '').replace('\r', '')
        path = repo.split('/')
        bareclone = str("git clone --mirror %s%s" % (gituri, repo))
        if (Utils.dir_exists_ex(path[1])) is False:
            self._shell.execute(bareclone, True)
        try:
            os.chdir(os.path.dirname(os.path.realpath(__file__)))
            Utils.xcopy(path[1], str("%s\\%s\\%s" % (Utils.home_dir(), REPO_BACKUP, path[1])))
            os.chdir(path[1])
        except Exception as ex1:
            Utils.printwf("Err: could not change to path %s : ex:%s" % (path[0], ex1.message))
    

    def do_bfg(self, push_to_repo=False):
        """do bfg cleanup on folder cloned as a bare repo"""
        merged = str("%s,%s" % (ExcludedFilesForGitV1, ExcludedFilesForGitV2))
        merged = merged.replace("\n",'')        
        bfg = str("java -jar ..\\bfg.jar --no-blob-protection --delete-files *.{%s}" % merged)
        expire = str("git reflog expire --expire=now --all")
        gc = str("git gc --prune=now --aggressive")
        push = str("git push")        
        Utils.printwf("<<<<<<<<<< Entering BFG mode >>>>>>>>>>")
        c = self._shell
        self._currentPID = c
        c.execute(bfg, True)
        Utils.printwf(c.std_out())
        c.execute(expire)
        Utils.printwf(c.std_out())
        os.system(gc)
        if push_to_repo is True:
            c.execute(push)
        Utils.printwf("<<<<<<<<<< Leaving BFG mode >>>>>>>>>>")

    
    def do_tag(self, remove_tag=False, applyFix=False, fixDirty=False, filter=None, enable_dump=False):
        """tag user commits with ABM commits.
        Latest user preceeding an abm array of commits will be tagged.
        First abm commit is internal and will be retrieved by finding Version.h and extract data from there.
        The other abm commits will be taken from the svn commit message.
        applyFix = True/False
        apply specifix abm fix: that given : ex. 
        there are 5 svn commits, but only 3 of them are present in GIT,
        apply tag from the lates 2 from svn to the latest in GIT 
        """
        #enter private region

        def find_file(dir, match):
            listOfFile = os.listdir(dir)
            allfiles = list()
            for entry in listOfFile:
                fullpath = os.path.join(dir, entry)
                if entry == match:
                    self.sresult = fullpath
                if os.path.isdir(fullpath):
                    allfiles = allfiles + find_file(fullpath, match)
                else:
                    allfiles.append(fullpath)
            return allfiles

        def parse_vh2(data):
            vminor, vmajor, vbranch, vfix, vminfix = -1, -1, -1, -1, -1
            for entry in data:
                entry_items = entry.split()

                if len(entry_items) != 3 or entry_items[0] != '#define':
                    continue
                vname = entry_items[1]
                version = entry_items[2]

                if vname.endswith("MAJOR_VERSION"):
                    vmajor = version
                elif vname.endswith("MINOR_VERSION"):
                    vminor = version
                elif vname.endswith("BRANCH_VERSION"):
                    vbranch = version
                elif vname.endswith("MIN_FIX_VERSION"):
                    vminfix = version
                elif vname.endswith("FIX_VERSION"):
                    vfix = version
 
            if vbranch >= 0 and vminfix >= 0 and vfix >= 0 and vminor >= 0 and vmajor >= 0:
                vh =  SvnGitMixin.versionh_t(major=vmajor, minor=vminor, branch=vbranch, fix=vfix, minfix=vminfix)
                return vh
            return None

        def exp_get_ver(r,opdir):
            fullpath = str("%s\\%s\\%s\\%s" % (Utils.home_dir(), ABM_TEMP, opdir, str(r)))
            exp = str("svn export -r %s %s %s" % (r,  self._svnpath, fullpath))
            self._shell.execute(exp)
            vh = None
            try:
                fullpath = str("%s\\%s" % (fullpath, "inc"))
                os.chdir(fullpath)
                find_file(fullpath, "Version.h")
                res = self.sresult
                if res is not None:
                    fp = open(res, "r")
                    lines = fp.readlines()
                    fp.close()            
                    vh = parse_vh2(lines)    #test
            except Exception as ex1:
                Utils.printwf(str("do_tag.exp_get_ver: %s" % ex1.message))
                pass
            self.sresult = None
            return vh
        
        def tag(tagname, commithash, vermsg):
            commit = str("git tag -a %s %s -m \"%s\"" % (tagname, commithash, vermsg))
            push = str("git push origin %s" % tagname)
            Utils.dump(str("INFO: %s" %commit))
            if SVNGIT_UPDATE_DB_ONLY is False:
                self._shell.execute(commit)
                self._shell.execute(push)

        def untag(tag):
            deltag = str("git tag -d %s" % tag)
            Utils.dump(str("INFO: %s" %deltag))
            pushdel = str("git push origin :refs/tags/%s" % tag)
            self._shell.execute(deltag)
            self._shell.execute(pushdel)
            
        def parse_ver_msg(data):
            spl = data.split()
            return spl

        def build_cm_msg(data, match):
            tmp = str()
            for i in range(data.index(match)+1, len(data)):
                tmp += str(" %s " % data[i])
            tmp = tmp.replace("  ", " ")
            fix = str("Automatic ABM commit:%s" % tmp)
            return fix
        
        def filter_fix_tag(data):
            """reorganize ABM commit that needs to be fixed"""
            ret = {}
            ret['nok'] = list()
            ret['ok'] = list()
            i, j = 0, 0
            
            while i < len(data):
                if Helpers.match_abm(data[i][1]):
                    ret['nok'].append(data[i])
                    i+= 1
                else:
                    break
            j = i
            while j < len(data):
                ret['ok'].append(data[j])
                j += 1
            return ret

        def apply_abm_fix(abmdata, opdir, utag=False, svnrev=None, topabm=0):
            i, size = 1, 0
            size = len(abmdata)
            if size > 0:
                commithashi = 0
                k = abmdata[len(abmdata)-1][0]
                self._set_path(self._gitpath)
                versionh2 = exp_get_ver(svnrev, opdir)
                self._set_path(self._gitpath)
                deltag = versionh2.to_tag()
                if k not in self._metagit:
                    commithashi = self._metagit[topabm] 
                else:
                    commithashi = self._metagit[k]
                commithashi = commithashi[0].split('\n')[0]
                cmmsgi = str("Automatic ABM commit: Increase Component version to: %s.%s.%s.%s" % (versionh2.majorv, versionh2.minorv, versionh2.branchv, versionh2.fixv))

                if utag:
                    untag(deltag)
                else:
                    Utils.db.add_tag(self._currentBranch, deltag)
                    tag(deltag, commithashi, cmmsgi)
                    
                while i < size:
                    commithash = 0 
                    if k not in self._metagit:
                        commithash = self._metagit[topabm]
                    else:
                        commithash = self._metagit[k]
                    commithash = commithash[0].split('\n')[0]
                    cmmsg = parse_ver_msg(abmdata[i][1])
                    tagname = cmmsg[22].replace('.', '_')
                    cmmsg = build_cm_msg(cmmsg, 'commit:')
                    if utag:
                        untag(tagname)
                    else:
                        tag(tagname, commithash, cmmsg)
                    i += 1
                return True
            else:
                Utils.dump("INFO: nothing to fix for ABM tags")
                return False

        def get_tag_by_user(commiter='yyordanov'):
            Utils.printwf(str("Start fix on repo %s w user %s " % (self._repo, commiter)))
            cm = str("git show-ref --tags")
            self._shell.execute(cm)
            spl = self._shell.std_out().split('\n')
            tags = []
            for entry in spl:
                hash_commit = entry.split()
                if len(hash_commit) > 1:
                    tag =  hash_commit[1].split('/')[2]
                    tags.append((hash_commit[0], tag))
            i = 0
            while i < len(tags):
                cm = str("git show %s" % tags[i][1])
                self._shell.execute(cm)
                if commiter in self._shell.std_out():
                    try:
                        svn = self._shell.std_out().split('git-svn-id:')[1].split('@')[1].split()[0]
                    except:
                        return (None, None, None, None)
                    
                    cm2 = str("git tag -n9")
                    self._shell.execute(cm2)
                    spl2 = self._shell.std_out().split('\n')
                    for ii in spl2:
                        spl3 = ii.split()                        
                        if len(spl3) > 0 and tags[i][1] == spl3[0]:
                            cmmmsg = " ".join(spl3[1:])
                            return (tags[i][0], svn, spl3[0], cmmmsg)
                i += 1

            return (None, None, None, None)

        #leave private region 

        Utils.printwf(str("Enter tag/untag mode for repo [%s]" % self._repo))
        Utils.dump(str("INFO: Enter tag/untag mode for repo [%s]" % self._repo))
       
        r = self._repo.replace("\n", '').replace("\r", '')
        r = r.split(',')
        opdir = r[-1]
        abmcommit = []
        #check if raw log is ok:
        #removed --no-walk  option and --pretty=\"%h %d %s\"
        #" --tags  --decorate=full --date=short"
        haslog = self.gitlog()
        
        if self._git_forward_err is True and remove_tag is False:
            Utils.printwf("Git repo ahead of SVN")
            Utils.dump("ERROR: Git repo ahead of SVN")
            return ERROR

        gitmeta = self._metagit
        if len(gitmeta) == 0 and haslog is False:
            Utils.dump("ERROR: NO_CONNECTION_TO_GIT")
            return  NO_CONNECTION_TO_GIT

        self._hkgit = self.hwm(gitmeta)
        git_abm_top_internal, git_abm_top = 0, 0
        gititems = gitmeta.items()
        gititems.sort()

        for i in range(len(gititems)):
            if Helpers.match_abm_aligned(gititems[i][1][0]):
                git_abm_top_internal = gititems[i][0]
            elif Helpers.match_abm(gititems[i][1][0]):
                git_abm_top = gititems[i][0]


        if git_abm_top_internal > 0:
            self.svnlog(str(git_abm_top_internal))
        else:
            return ERROR_INSUFFICIENT_CLONE_DEPTH

        svnitems = self._metasvn.items()
        if len(svnitems) == 0:
            Utils.dump("ERROR: NO_CONNECTION_TO_SVN")
            return NO_CONNECTION_TO_SVN        

        #TODO: get the latest saved SVN rev
        currentSavedRev = Utils.db.get_svnrev(self._currentBranch)
        hsvn = self.hwm(self._metasvn)
        if hsvn == currentSavedRev:
            Utils.printwf("Current GIT state and SVN state are equal. Nothing to do.")
            return OK
        
        Utils.db.add_svnrev(self._currentBranch, hsvn)

        svnitems.sort()
        latestuser = None
        dAbmMan = filter_fix_tag(svnitems)
        svnitems = dAbmMan['ok']
        tobefix = dAbmMan['nok']
        if len(tobefix) > 0:
            apply_abm_fix(tobefix, opdir, remove_tag, tobefix[-1][0], git_abm_top)

        if FIX_DIRTY_TAGS_SPECIAL: #remove after all tags are fixed !!!
            commithashfix, svnrev, dirtytag, oldmessage = get_tag_by_user()
            if commithashfix is not None and svnrev is not None and dirtytag is not None and oldmessage is not None:
                versionh2 = exp_get_ver(svnrev, opdir)
                self._set_path(self._gitpath)
                untag(dirtytag)
                dirtytag = versionh2.to_tag()
                tag(dirtytag, commithashfix, oldmessage)
                return OK
            else:
                return OK

        i = 0
        if len(svnitems) == 0:
            Utils.dump("INFO: Nothing to tag SVN and GIT are synched")

        #devide and conquer algo to organize manuals and automatic commits
        while  i < len(svnitems):

            while i < len(svnitems):
                if Helpers.match_abmasmanual(svnitems[i][1]) is True:
                    latestuser = svnitems[i]
                    i += 1
                elif Helpers.match_abm(svnitems[i][1]) is False:
                    latestuser = svnitems[i]
                    i += 1
                else:
                    break
                        
            while i < len(svnitems) and Helpers.match_abm(svnitems[i][1]) is True:                   
                abmcommit.append(svnitems[i])
                i += 1
                
            if len(abmcommit) > 0 and latestuser is not None:
                #get only the first abm commit - internal and parse the version.h file for it
                #for all other abm commits - external, we append the commit message and version taken from the svn log parse
                # the inner apply_abm_fix() shall handle abm to abm cases
                vermsg = parse_ver_msg(abmcommit[0][1])
                versionh = exp_get_ver(abmcommit[0][0], opdir)

                if versionh is not None:
                    k = int(latestuser[0])
                    if k in self._metagit:
                        commithash = self._metagit[k]
                        commithash = commithash[0].split('\n')[0]
                        tagname = versionh.to_tag()
                        vermsg = build_cm_msg(vermsg, 'commit:')
                        self._set_path(self._gitpath)
                        Utils.db.add_tag(self._currentBranch, tagname)
                        if remove_tag is True:
                            untag(tagname)
                        else:
                            tag(tagname, commithash, vermsg)
                        
                        for ii in range(1, len(abmcommit)):
                            cmmsg = parse_ver_msg(abmcommit[ii][1])
                            tagname2 = cmmsg[22].replace('.', '_')
                            cmmsg = build_cm_msg(cmmsg, 'commit:')
                            if remove_tag is True:
                                untag(tagname2)
                            else:
                                tag(tagname2, commithash, cmmsg)
                            pass
                        del(abmcommit)
                        abmcommit = None
                        abmcommit = []
                        latestuser = None
                    else:
                        Utils.printwf(str("%s revision from svn is not present in git " % k))
                        Utils.dump(str("ERROR: %s revision from svn is not present in git " % k))
                else:
                    Utils.dump("ERROR: Unable to compile tag from version.h file")
        return OK #by convention always return OK since do_tag can't retuyrn error state


    def dumpn9(self):
        updatetags = str("git pull --tags")
        n9 = str("git tag -n9")
        self._shell.execute(updatetags)
        self._shell.execute(n9)
        Utils.printwf(self._shell.std_err())
        Utils.printwf(self._shell.std_out())        
        pass


    def do_merge(self, date, cleanup=True):
        """ merge svn repo to git """
        Utils.printwf("Entering a merging procedure")
        r = self._repo.replace("\n", '').replace("\r", '')
        haslog = self.gitlog(" --date=short")
        gitmeta = self._metagit
        if len(gitmeta) == 0 and haslog is False:
            Utils.dump(str("ERROR: NO_CONNECTION_TO_GIT"))
            return  NO_CONNECTION_TO_GIT

        self._hkgit = self.hwm(gitmeta)
        self.svnlog(str(self._hkgit))
        
        svnmeta = self._metasvn
        if len(svnmeta) == 0:
            Utils.dump(str("ERROR: NO_CONNECTION_TO_SVN"))
            return NO_CONNECTION_TO_SVN
        self._hksvn = self.hwm(svnmeta)  
        
        if self._hksvn in gitmeta:
            #Utils.dump(str("[Up to date repo],%s" % r))
            return OK
        else:
            pass
            #Utils.dump(str("[Needs fix],%s,git,%s,svn,%s" % (r, self._hkgit, self._hksvn))) 
        # sort the versions before exporting so you can add them to git in increasing order
        pydir = str(os.path.dirname(os.path.realpath(__file__)))       
        postf = r.split(',')[2]
        postf = postf.replace("/", "\\")

        sorted(svnmeta.keys())
        items = svnmeta.items()
        items.sort()
        rootdir = None
        for i  in items:
            k = i[0]
            msg = i[1].split("\r\n\r\n")
            msg[1] = msg[1].replace("\r\n", ' ')
            spl = i[1].split()
            if len(spl) > 4 and k != int(self._hkgit):
                Utils.dump(str("INFO: %s, %s, %s, %s, %s" % (r, k, spl[2], spl[4], msg[1])))

                if spl[2].lower() == "abm" and msg[1].find("Automatic ABM commit") is not -1:
                    pass #do nothing for now if ABM commit and automatic commit, careful now, since ABM user might be manual too
                elif spl[2].lower() in GUserMails:
                    repo = None
                    if TEST_GIT_REPO_NAME is not None:
                        repo = self.init_branch(TEST_GIT_REPO_NAME, cleanup)
                    else:
                        os.chdir(self._gitpath) # go to dir path
                        exppath = str("%s\\%s\\%s" % (pydir, postf, k))
                        rootdir = str("%s\\%s" % (pydir, postf))
                        c = self._shell
                        self._currentPID = c                        
                        exp = str("svn export -r %s %s %s" % (k,  self._svnpath, exppath))
                        c.execute(exp)
                        # copy and commit - do the actual merge with ver                                 
                        if Utils.xcopy(exppath, self._gitpath) is True:
                            full_msg = str("%s\r\nsvn-revision:%s\r\n" % (msg[1], k))
                            full_msg = full_msg.replace("\"", "\'")
                            you_mail = str(GUserMails[spl[2].lower()])
                            self.add_and_commit(spl[2], you_mail, spl[4], full_msg, repo)
                        else:                        
                            Utils.printwf(str("Error: Repositories: %s and %s are probably deleted." % (self._repo, self._svnuri)))
                            Utils.dump(str("Error: Repositories: %s and %s are probably deleted." % (self._repo, self._svnuri)))                            
                            Utils.rmdir(rootdir) 
                            return ERROR
                else:
                    Utils.printwf(str("Error: Mail %s not in the mailing list, aborting migration" % spl[2]))
                    Utils.dump(str("Error: Mail %s not in the mailing list, aborting migration" % spl[2]))
                    break
        Utils.rmdir(rootdir) #finally delete export dir
        return OK


    def svn_checkout(self):
        os.chdir(str("%s\\%s" % (Utils.home_dir() , SVN_TEMP_DIR)))
        spl = self._svnuri.split("/")
        reponame = spl[len(spl)-1]
        checkout = str("svn checkout %s" % self._svnuri)
        self._svnpath = str("%s\\%s\\%s" % (Utils.home_dir(), SVN_TEMP_DIR, reponame))
        c = self._shell
        c.execute(checkout)
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        pass


    def git_clone(self, path, branch, depth, rmdir=False):
        """ uri, branch, depth """
        try:
            os.chdir(str("%s\\%s" % (Utils.home_dir() , GIT_TEMP_DIR)))         
            clone = str("git clone --depth %s --single-branch --branch %s %s%s %s" % (depth, branch, self._gituri, path, branch))
            self._currentBranch = branch
            checkout = str("git checkout %s" % branch)
            pull = str("git pull")
            self._gitpath = str("%s\\%s\\%s" % (Utils.home_dir(), GIT_TEMP_DIR, branch))
            c = self._shell
            if rmdir is True:
                Utils.rmdir(self._gitpath)
            c.execute(clone)
            os.chdir(self._gitpath)
            c.execute(checkout)
            c.execute(pull)
            os.chdir(os.path.dirname(os.path.realpath(__file__)))
            Utils.db.add_record(self._currentBranch)
        except Exception as ex1:
            Utils.printwf(str("Exception in git_clone: (%s)" % ex1.message))
            pass    

    
    def xml_tag(self):

        def validate_tag(data):
            ver, name = self._xmlContext.get_vername()
            xmlver = self._xmlContext.get_attrib_by_name(name).attrib['Version']
            tmp = data.split('/')[2]
            ver = ver.split('_')
            tmp = tmp.split('_')
            if len(tmp) == 4:         
                if tmp[3] == xmlver:           
                    return int(tmp[3])
                else:
                    Utils.dump(str("ERROR: Version mismatch XML: %s \t GIT: %s" % (xmlver, tmp[3])))
                    return -1
            return -1 
               
        highest_tag = -1
        latest_hash = None
        os.chdir(self._gitpath)
        c = str("git show-ref --tags")
        self._shell.execute(c)

        if self._shell.std_out() is None:
            Utils.printwf(str("No tags for %s" % self._repo))
            return
            
        entries = self._shell.std_out().split('\n')
        for entry in entries:
            spl = entry.split()
            if len(spl) == 2:
                tag = spl[1]
                htag = validate_tag(tag)
                if htag > highest_tag:
                    highest_tag = htag
                    latest_hash = spl[0]

        _, name = self._xmlContext.get_vername()
        self._xmlContext.update(name, latest_hash)
        pass 
    

    def remove_tags(self):
        os.chdir(self._gitpath)
        Utils.printwf(str("Tags to be removed from repo %s %s" % (self._repo, self._tags)))
        updatetags = str("git pull --tags")
        self._shell.execute(updatetags)
        deleted = 0
        if self._tags is not None:
            for tag in self._tags:
                deltag = str("git tag -d %s" % tag)
                pushdel = str("git push origin :refs/tags/%s" % tag)
                Utils.dump(str("INFO: %s" % deltag))
                self._shell.execute(deltag)
                self._shell.execute(pushdel)
                Utils.printwf(str("err:%s\tout:%s" % (self._shell.std_err(), self._shell.std_out())))
                Utils.dump(str("INFO: err:%s\tout:%s" % (self._shell.std_err(), self._shell.std_out())))
                deleted += 1
        return deleted


    def finish(self):
        if self._xmlContext is not None:
            self._xmlContext.finalize()    
            self._xmlContext = None    


    def update_platforms(self):
        """ update components version xml with commithashes based on tags... """
        if self._xmlContext is None:
            self._xmlContext = GXml     
        Utils.printwf(str("[%s][%s]" % (self._gitpath, self._repo)))
        spl = self._repo.split(',')[2].split('_')
        ver = str("%s_%s_%s" % (spl[1], spl[2], spl[3]))
        name = spl[0]
        self._xmlContext.set_vername(ver, name)        
        self.xml_tag()
        pass


    def abort(self):
        if self._shell is not None:
            self._shell.kill()
            self._shell = None


    def terminate(self):
        pass


    def end(self):
        pass

#end region SvnGitMixin


#TODO: use it if multitreading mode is on
def thread_proxy(svn_, git_, branch_):
    """EXPERIMENTAL: thread proxy function"""
    mix = None
    try:                    
        svn = svn_
        branch = branch_
        git = git_
        mix = SvnGitMixin(svnuri=svn, gituri=CSI_GIT_URI, svnpath=None, gitpath=None)
        #TODO: hande args when done
        mix.git_clone(git, branch, 10)
        mix.svn_checkout()
        mix.set_current("%s,%s,%s"% (svn, git, branch))
        mix.finish()
    except:                    
        mix.abort()
    pass



###################################################### MAIN ######################################################
if __name__ == "__main__":

    if Utils.db.load('db.json') is True:
        Utils.printwf("OK, loaded db file")

    def _intag(mix,svn,git,branch,depth,remtag=False):
        while mix.do_tag(remove_tag=remtag, applyFix=True) == ERROR_INSUFFICIENT_CLONE_DEPTH:
            Utils.printwf("Insufficient git depth. Could not obtain meaningful info.Now reclone with depth (%s)" % int(depth * 2))
            depth = 2 * depth
            mix.git_clone(git, branch, depth, rmdir=True)
            mix.svn_checkout()                    
            mix.set_current("%s,%s,%s" % (svn, git, branch))
        pass

    def _idump(mix,svn,git,branch,dumpall=False):
        if dumpall is True:
            Utils.printwf(str("%s,%s,%s" % (svn, git, branch)))
            mix.gitlog()
            mix.dumpn9()

    GXml = None #XmlUpdateContext('C:\\Users\\izapryanov\\Desktop\\tools\\ComponentsVersions.xml')
    merged = str("%s,%s" % (ExcludedFilesForGitV1, ExcludedFilesForGitV2))
    merged = merged.replace("\n",'')        
    args = {}
    args.update({'--option' : None})
    args.update({'--bfg':None})    
    args.update({'--file':None})
    args.update({'--merge':None})
    args.update({'--clean':None})
    args.update({'--optimize':None})
    args.update({'--help' : HELP_MESSAGE})    
    args.update({'--nolog':None})
    args.update({'--tag' : None})
    args.update({'--untag' : None})
    args.update({'--xml-file' : None})
    args.update({'--fix-dirty' : None})
    args.update({'--export-platforms' : None})
    args.update({'--fullmerge' : None})
    args.update({'--dump-all' : None})
    args.update({'--purge-tags' : None})
    args.update({'--update-db' : None})
    args.update({'--abm' : None})

    start_time = datetime.datetime.now().time().strftime('%H:%M:%S')

    with open('eml.json', 'r') as fp:
        GUserMails = json.load(fp)
    
    if GUserMails is None:
        Utils.printwf("No mail list loaded")
        sys.exit(-1)

    for i in range(len(sys.argv)):
        if sys.argv[i] == "--help":
            Utils.printwf(HELP_MESSAGE)
            sys.exit(0)
        args.update({str(sys.argv[i]):i})        
       
    if args['--nolog'] is not None:
        LOG_DISABLED = True

    # we need do bfg with file .platform.comps
    #DELETE the True and uncomment the args 
    if args['--xml-file'] is not None:
        GXml = XmlUpdateContext(sys.argv[args['--xml-file']+1])
    else:
        GXml = None
    

    if args['--bfg'] is not None and args['--file'] is not None:
        Utils.printwf("Entering 'BFG' mode...")
        pcomps = sys.argv[args['--file']+1] # uncomment in release
        try:
            fp = open(pcomps, "r")
            lines = fp.readlines()
            fp.close()
        except Exception as pcomsex:
            Utils.printwf(str("File (%s) not found expception: ex:%s" % (pcomps, pcomsex.message)))
            sys.exit(-2)
        Utils.mkdir(REPO_BACKUP)
        bfg = None
        for line in lines:
            try:
                spl = line.split(',')
                repo = spl[1]
                bfg = SvnGitMixin()
                bfg.clone_bare(CSI_GIT_URI, repo)
                bfg.do_bfg()
                bfg.terminate()
            except:
                Utils.printwf("User interrupt caught")
                bfg.abort()
                sys.exit(-1)
    else:

        if args['--fix-dirty'] is not None:
            FIX_DIRTY_TAGS = True
        else:
            FIX_DIRTY_TAGS = False

        clean = False
        
        
        if args['--clean'] is not None:
            clean = True
        # is not None later 
        elif args['--file'] is not None:   
            if GDEBUG is True: #debug stuff only
                Utils.printwf("Enter debug mode")
                Utils.load_svngit('svngitex.txt')
            else:       
                Utils.load_svngit(sys.argv[args['--file']+1])

            Utils.mkdir(GIT_TEMP_DIR)
            Utils.mkdir(SVN_TEMP_DIR)
            Utils.mkdir(ABM_TEMP)
            Utils.printwf(str("Starting migrating mode V2 w args [%s]\r\n" % args))
            Utils.printwf("This may take a while... please wait...\r\n")
            mix = None
        
            for entry in GSvnGitMeta:      
                depth = GDepth          
                Utils.printwf("###############################################################")
                try:
                    tags = None
                    if 'tags' in entry: #tags are optional 
                       tags = entry['tags']
                    svn = entry['svn']
                    branch = entry['branch']
                    git = entry['git']
                    mix = SvnGitMixin(svnuri=svn, gituri=CSI_GIT_URI, svnpath=None, gitpath=None, opt_tags=tags)                        
                    mix.git_clone(git, branch, 20)
                    mix.svn_checkout()                    
                    mix.set_current("%s,%s,%s" % (svn, git, branch))
                    Utils.dump("---------------------------------------------------------------------------")
                    Utils.dump(str("INFO: %s,%s,%s" % (svn, git, branch)))
                    bDumpAll = False
                    if GDEBUG is False:

                        if args['--update-db'] is not None:
                            SVNGIT_UPDATE_DB_ONLY = True
                        
                        if args['--abm'] is not None:
                            SVNGIT_ON_ABM = True

                        if args['--dump-all'] is not None:
                            bDumpAll = True
                        if args['--tag'] is not None:
                            _intag(mix,svn, git, branch, depth)
                        elif args['--untag'] is not None:
                            _intag(mix,svn, git, branch, depth, remtag=True)
                        elif args['--merge'] is not None:
                            mix.do_merge("{2019-01-01}", cleanup=clean)
                        elif args['--export-platforms'] is not None and GXml is not None:
                            mix.update_platforms()
                        elif args['--fullmerge'] is not None:
                            mix.do_merge("{2019-01-01}", cleanup=clean)
                            _intag(mix, svn, git, branch, depth)
                        elif args['--purge-tags'] is not None:
                            mix.remove_tags()
                        else:
                            mix.finish()
                        _idump(mix, svn, git, branch, bDumpAll)
                        mix.finish()
                    else:
                        _intag(mix, svn, git, branch,depth)
                        pass
                    mix.finish()
                except Exception as mainEx:                    
                    Utils.printwf(str("Exception from main caught: %s" % mainEx.message))

            end_time = datetime.datetime.now().time().strftime('%H:%M:%S')
            total_time=(datetime.datetime.strptime(end_time,'%H:%M:%S') - datetime.datetime.strptime(start_time,'%H:%M:%S'))
            Utils.printwf(str("Script finished. Time elapsed: (%s) " % total_time))
        else:
            Utils.printwf(str("Unknow arguments or usage %s " % args))
            Utils.printwf("See 'help' for more info")

    Utils.finalize()

#######################################################################################################################################
# todo:

#######################################################################################################################################
#bdata section (put binary or RO data below) w/marker tag