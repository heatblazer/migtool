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
from Utils import Utils
from Shell import Cmd
from Helpers import Helpers
from Helpers import XmlUpdateContext
from Helpers import Functor
from Helpers import PThread
from Globals import NS
import json
import time
from time import sleep
import os
import sys
import warnings


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

        def __str__(self):
            return self.to_tag()

    ##################################################################

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
        self._repos = []       
        self._currentPID = None
        self._currentBranch = None
        self._shell = Cmd()
        self.sresult = None
        self._xmlContext = None
        self._git_forward_err = False
        self._tags = opt_tags # buffer all tags here
        self._doNotTag = False
        self._hasNoAbm = False
        self._hasError = False
    

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

    def get_tag_by_user(self, commiter='yyordanov'):
        Utils.printwf(str("Start fix on repo %s w user %s " % (self._repo, commiter)))
        cm = str("git show-ref --tags -d")
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
        if NS.TEST_GIT_REPO_NAME is not None:
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
            Utils.xcopy(path[1], str("%s\\%s\\%s" % (Utils.home_dir(), NS.REPO_BACKUP, path[1])))
            os.chdir(path[1])
        except Exception as ex1:
            Utils.printwf("Err: could not change to path %s : ex:%s" % (path[0], ex1.message))
    

    def do_bfg(self, push_to_repo=False):
        """do bfg cleanup on folder cloned as a bare repo"""
        merged = str("%s,%s" % (NS.ExcludedFilesForGitV1, NS.ExcludedFilesForGitV2))
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


    def get_latestcommit(self):
        if self._metagit is not None and len(self._metagit) > 0:
            it = self._metagit.items()
            it.sort()
            return it[-1]

    
    def do_tag(self, remove_tag=0, applyFix=False, fixDirty=False, filter=None, enable_dump=False):
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
            fullpath = str("%s\\%s\\%s\\%s" % (Utils.home_dir(), NS.ABM_TEMP, opdir, str(r)))
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
            if NS.SVNGIT_UPDATE_DB_ONLY is False:
                Utils.db.add_tag(self._currentBranch, tagname)
                self._shell.execute(commit)
                self._shell.execute(push)
            else:
                Utils.printwf("[TAG]Update db only...")

        def untag(tag):
            deltag = str("git tag -d %s" % tag)
            Utils.dump(str("INFO: %s" %deltag))
            pushdel = str("git push origin :refs/tags/%s" % tag)
            if NS.SVNGIT_UPDATE_DB_ONLY is False:
                self._shell.execute(deltag)
                self._shell.execute(pushdel)
            else:
                Utils.printwf("[UNTAG]Update db only...")

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
            if self._hasNoAbm:
                ret['ok'] = data
                return ret    
            
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

        def apply_full_merge_fix(abmdata, svnrev, opdir, topabm):
            size, j, commithashi, k = len(abmdata), 0, 0, 0
            abmdata.sort()
            sortedabm = list(abmdata)
            todotag = []
            i = size -1
            if size == 0:
                return 
            while i >=0:
                if Helpers.match_abm(sortedabm[i][1]):
                    todotag.append(sortedabm[i])
                elif Helpers.match_abm_aligned(sortedabm[i][1]):
                    todotag.append(sortedabm[i])
                else:
                    break #foudn manual
                i-=1

            if len(todotag) > 0:
                j = len(todotag) -1
                commithashi = 0
                k = todotag[0][0]
                self._set_path(self._gitpath)
                versionh2 = exp_get_ver(svnrev, opdir)
                self._set_path(self._gitpath)
                commithashi = self._metagit[k]
                commithashi = commithashi[0].split('\n')[0]
                deltag = versionh2.to_tag()
                cmmsgi = str("Automatic ABM commit: Increase Component version to: %s.%s.%s.%s" % (versionh2.majorv, versionh2.minorv, versionh2.branchv, versionh2.fixv))
                tag(deltag, commithashi, cmmsgi)

                ii = j-1
                while ii >=0:
                    commithash = self._metagit[k]
                    commithash = commithash[0].split('\n')[0]
                    cmmsg = parse_ver_msg(todotag[ii][1])
                    tagname = cmmsg[22].replace('.', '_')
                    cmmsg = build_cm_msg(cmmsg, 'commit:')
                    tag(tagname, commithash, cmmsg)
                    ii-=1

            pass

        def apply_abm_fix(abmdata, opdir, utag=0, svnrev=None, topabm=0):
            i, size = 1, 0
            size = len(abmdata)
            abmdata.sort()
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

                if utag == 1:
                    untag(deltag)
                elif untag == 2:
                    untag(deltag)
                    tag(deltag, commithashi, cmmsgi)
                else:
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
                    if utag == 1:
                        untag(tagname)
                    elif utag == 2:
                        untag(tagname)
                        tag(tagname, commithash, cmmsg)
                    else:
                        tag(tagname, commithash, cmmsg)
                    i += 1
                return True
            else:
                Utils.dump("INFO: nothing to fix for ABM tags")
                return False
        
        #leave private region 
        #Utils.db.clear_tags(self._currentBranch)
        Utils.printwf(str("Enter tag/untag mode for repo [%s]" % self._repo))
        Utils.dump(str("INFO: Enter tag/untag mode for repo [%s]" % self._repo))
        if self._hasError:
            return NS.Errors.ERROR
        #get the current svn saved state
        currentSavedRev = Utils.db.get_svnrev(self._currentBranch) 
        hsvn = 0 #highest svn
        r = self._repo.replace("\n", '').replace("\r", '')
        r = r.split(',')
        opdir = r[-1]
        opdir = opdir.replace(' ', '')
        abmcommit = []
        #check if raw log is ok:
        #removed --no-walk  option and --pretty=\"%h %d %s\"
        #" --tags  --decorate=full --date=short"
        haslog = self.gitlog()
        
        if self._git_forward_err is True and remove_tag != 1:
            Utils.printwf("Git repo ahead of SVN")
            Utils.dump("ERROR: Git repo ahead of SVN")
            return NS.Errors.ERROR

        gitmeta = self._metagit
        if len(gitmeta) == 0 and haslog is False:
            Utils.dump("ERROR: NO_CONNECTION_TO_GIT")
            return  NS.Errors.NO_CONNECTION_TO_GIT

        self._hkgit = Helpers.hwm(gitmeta)
        git_abm_top_internal, git_abm_top = 0, 0
        gititems = gitmeta.items()
        gititems.sort()

        for i in range(len(gititems)):
            if Helpers.match_abm_aligned(gititems[i][1][0]):
                git_abm_top_internal = gititems[i][0]
            elif Helpers.match_abm(gititems[i][1][0]):
                git_abm_top = gititems[i][0]

        #TODO: review this
        if currentSavedRev > 0 and NS.BFORCE_ALL is False:
            Utils.printwf("INFO: Will use %s as clone mark" % currentSavedRev)
            self.svnlog(str(currentSavedRev)) #get the last rev from db
            hsvn = Helpers.hwm(self._metasvn)
            if hsvn == currentSavedRev and remove_tag==0:
                Utils.printwf("INFO: Current GIT state and SVN state are equal. Nothing to do.")
                return NS.Errors.OK

        if git_abm_top_internal == 0 and git_abm_top > 0 and currentSavedRev == 0:
            return NS.Errors.ERROR_INSUFFICIENT_CLONE_DEPTH

        if True: #socped check !!!!
            if git_abm_top_internal >= 0:
                if git_abm_top < currentSavedRev:
                    self.svnlog(str(currentSavedRev))
                else:
                    self.svnlog(str(git_abm_top_internal))
            else:
                if git_abm_top_internal == 0 and git_abm_top == 0:
                    self._hasNoAbm = True
                    Utils.printwf("WARN: No ABM commits in git repo.")
                    self.svnlog(str(currentSavedRev)) # get the upper git present in svn
                else:
                    return NS.Errors.ERROR_INSUFFICIENT_CLONE_DEPTH
            
        svnitems = self._metasvn.items()
        if len(svnitems) == 0:
            Utils.dump("ERROR: NO_CONNECTION_TO_SVN")
            return NS.Errors.NO_CONNECTION_TO_SVN        

        svnitems.sort()
        latestuser = None
        dAbmMan = filter_fix_tag(svnitems)
        svnitems = dAbmMan['ok']
        tobefix = dAbmMan['nok']

        if self._hasNoAbm is False:
            if self._hkgit == hsvn:
                apply_full_merge_fix(self._metasvn.items(), git_abm_top_internal, opdir, git_abm_top)
                Utils.db.add_svnrev(self._currentBranch, Helpers.hwm(self._metasvn))
                return NS.Errors.OK
            elif len(tobefix) > 0:
                apply_abm_fix(tobefix, opdir, remove_tag, tobefix[-1][0], git_abm_top)            
            Utils.db.add_svnrev(self._currentBranch, Helpers.hwm(self._metasvn)) #record the highst svn in db 
        else:
            Utils.db.add_svnrev(self._currentBranch, Helpers.hwm(currentSavedRev)) #keep the old


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
                        if remove_tag == 1:
                            untag(tagname)
                        elif remove_tag == 2:
                            untag(tagname)
                            tag(tagname, commithash, vermsg)
                        else:
                            tag(tagname, commithash, vermsg)
                        
                        for ii in range(1, len(abmcommit)):
                            cmmsg = parse_ver_msg(abmcommit[ii][1])
                            tagname2 = cmmsg[22].replace('.', '_')
                            cmmsg = build_cm_msg(cmmsg, 'commit:')
                            if remove_tag == 1:
                                untag(tagname2)
                            elif remove_tag == 2:
                                untag(tagname2)
                                tag(tagname2, commithash, cmmsg)
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
        return NS.Errors.OK #by convention always return OK since do_tag can't retuyrn error state


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
        if self._hasError:
            return NS.Errors.ERROR

        r = self._repo.replace("\n", '').replace("\r", '')
        Utils.printwf("INFO: Entering a merging procedure on [%s]" % r)

        haslog = self.gitlog(" --date=short")
        gitmeta = self._metagit
        if len(gitmeta) == 0 and haslog is False:
            Utils.dump(str("ERROR: NO_CONNECTION_TO_GIT"))
            return  NS.Errors.NO_CONNECTION_TO_GIT

        self._hkgit = Helpers.hwm(gitmeta)
        self.svnlog(str(self._hkgit))
        
        svnmeta = self._metasvn
        if len(svnmeta) == 0:
            Utils.dump(str("ERROR: NO_CONNECTION_TO_SVN"))
            return NS.Errors.NO_CONNECTION_TO_SVN
        self._hksvn = Helpers.hwm(svnmeta)  
        
        if self._hksvn in gitmeta:
            Utils.printwf("INFO: nothing to merge...")
            return NS.Errors.OK
        
            #Utils.dump(str("[Needs fix],%s,git,%s,svn,%s" % (r, self._hkgit, self._hksvn))) 
        # sort the versions before exporting so you can add them to git in increasing order
        pydir = str(os.path.dirname(os.path.realpath(__file__)))       
        postf = r.split(',')[2]
        postf = postf.replace("/", "\\")

        sorted(svnmeta.keys())
        items = svnmeta.items()
        items.sort()
        for i  in items:
            k = i[0]
            msg = i[1].split("\r\n\r\n")
            msg[1] = msg[1].replace("\r\n", ' ')
            spl = i[1].split()
            if len(spl) > 4 and k != int(self._hkgit):
                Utils.dump(str("INFO: %s, %s, %s, %s, %s" % (r, k, spl[2], spl[4], msg[1])))

                if Helpers.match_abm(i[1]) is True and NS.BFORCE_ALL is False: #spl[2].lower() == "abm" and msg[1].find("Automatic ABM commit") is not -1:
                    continue #do nothing for now if ABM commit and automatic commit, careful now, since ABM user might be manual too
                
                if spl[2].lower() in GUserMails:
                    repo = None
                    if NS.TEST_GIT_REPO_NAME is not None:
                        repo = self.init_branch(NS.TEST_GIT_REPO_NAME, cleanup)
                    else:
                        os.chdir(self._gitpath) # go to dir path
                        exppath = str("%s\\%s\\%s" % (pydir, postf, k))
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
                            return NS.Errors.ERROR
                else:
                    Utils.printwf(str("Error: Mail %s not in the mailing list, aborting migration" % spl[2]))
                    Utils.dump(str("Error: Mail %s not in the mailing list, aborting migration" % spl[2]))
                    break
        return NS.Errors.OK


    def svn_checkout(self):
        try:
            os.chdir(str("%s\\%s" % (Utils.home_dir() , NS.SVN_TEMP_DIR)))
            spl = self._svnuri.split("/")
            reponame = spl[len(spl)-1]
            checkout = str("svn checkout %s %s_%s" % (self._svnuri, reponame, spl[-1-1]))
            self._svnpath = str("%s\\%s\\%s_%s" % (Utils.home_dir(), NS.SVN_TEMP_DIR, reponame, spl[-1-1]))
            c = self._shell
            c.execute(checkout)
            os.chdir(os.path.dirname(os.path.realpath(__file__)))
            pass
        except Exception as ex1:
            Utils.printwf("Exception: ex in svn_checkoit(...)  %s" % ex1.message)
            self._hasError = True


    def git_clone(self, path, branch, depth, rmdir=False):
        """ uri, branch, depth """
        try:
            os.chdir(str("%s\\%s" % (Utils.home_dir() , NS.GIT_TEMP_DIR)))
            clone = None
            branch = branch.replace(' ', '')
            if NS.NO_GIT_URI:
                spl = path.split('/')
                fixpath = str("%s%s/%s" % (NS.CSI_GIT_URI, spl[-1-1], spl[-1]))
                clone = str("git clone --depth %s --single-branch --branch %s %s %s" % (depth, branch, fixpath, branch))                         
            else:
                clone = str("git clone --depth %s --single-branch --branch %s %s%s %s" % (depth, branch, self._gituri, path, branch))        
            

            self._currentBranch = branch
            checkout = str("git checkout %s" % branch)
            pull = str("git pull")
            self._gitpath = str("%s\\%s\\%s" % (Utils.home_dir(), NS.GIT_TEMP_DIR, branch))
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
            Utils.printwf(str("Exception: ex in git_clone: (%s)" % ex1.message))
            self._hasError = True
            pass    

    
    def xml_tag(self):
        """xml tag component with commithash of the highest tag"""
        def validate_tag(data):
            ver, name = self._xmlContext.get_vername()
            xmlver = self._xmlContext.get_attrib_by_name(name).attrib['Version']
            tmp = data.split('/')[2]
            ver = ver.split('_')
            tmp = tmp.split('_')
            if len(tmp) == 4:
                t = tmp[3].replace(r'^{}','')         
                if t == xmlver:           
                    return int(t)
                else:
                    return -1
            return -1 
               
        highest_tag = -1
        latest_hash = None
        os.chdir(self._gitpath)
        cpulltags = str("git pull --tags")
        cshowreftags = str("git show-ref --tags -d")
        self._shell.execute(cpulltags)
        self._shell.execute(cshowreftags)

        if self._shell.std_out() is None:
            Utils.printwf(str("No tags for %s" % self._repo))
            return
            
        entries = self._shell.std_out().split('\n')
        for entry in entries:
            spl = entry.split()
            if len(spl) == 2:
                if spl[1].endswith(r'^{}'):
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


################################################ MAIN ################################################
if __name__ == "__main__":
    Utils.printwf("*************************************************************************************************")
    #hardcoded file/path to the db
    if Utils.db.load('db.json') is True:
        Utils.home()
        Utils.printwf("INFO: OK, loaded db file")

    def _intag(mix,svn,git,branch,depth,tagopt=0):
        if tagopt == 0:
            Utils.printwf("Enter tag mode")
        elif tagopt == 1:
            Utils.printwf("Enter untag mode")
        elif tagopt == 2:
            Utils.printwf("Enter retag mode")
        else:
            Utils.printwf("Unknown option... Aborting...")
            return False
        while mix.do_tag(remove_tag=tagopt, applyFix=True) == NS.Errors.ERROR_INSUFFICIENT_CLONE_DEPTH:
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
    merged = str("%s,%s" % (NS.ExcludedFilesForGitV1, NS.ExcludedFilesForGitV2))
    merged = merged.replace("\n",'')        
    args = NS.Gargs

    start_time = datetime.datetime.now().time().strftime('%H:%M:%S')

    with open('eml.json', 'r') as fp:
        GUserMails = json.load(fp)
    
    if GUserMails is None:
        Utils.printwf("No mail list loaded")
        sys.exit(-1)

    for i in range(len(sys.argv)):
        if sys.argv[i] == "--help":
            Utils.printwf(NS.HELP_MESSAGE)
            sys.exit(0)
        args.update({str(sys.argv[i]):i})        
       
    if args['--nolog'] is not None:
        LOG_DISABLED = True

    # we need do bfg with file .platform.comps
    #DELETE the True and uncomment the args
    try: 
        if args['--xml-file'] is not None:
            GXml = XmlUpdateContext(sys.argv[args['--xml-file']+1])
        elif NS.GDEBUG is True:
            GXml = XmlUpdateContext("ComponentsVersions.xml")
        else:
            GXml = None
    except:
        Utils.printwf("WARNING: No Components Version loaded")

    if args['--users'] is not None:
        for user in GUserMails:
            Utils.printwf(user)

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
        Utils.mkdir(NS.REPO_BACKUP)
        bfg = None
        for line in lines:
            try:
                spl = line.split(',')
                repo = spl[1]
                bfg = SvnGitMixin()
                bfg.clone_bare(NS.CSI_GIT_URI, repo)
                bfg.do_bfg()
                bfg.terminate()
            except:
                Utils.printwf("User interrupt caught")
                bfg.abort()
                sys.exit(-1)
    else:

        if args['--fix-dirty'] is not None:
            NS.FIX_DIRTY_TAGS = True
        else:
            NS.FIX_DIRTY_TAGS = False
        clean = False
                

        if args['--clean'] is not None:
            clean = True
        # is not None later 
        elif args['--file'] is not None:   
            if NS.GDEBUG is True: #debug stuff only
                Utils.printwf("Enter debug mode")
                NS.NO_GIT_URI = True
                Utils.load_svngit('tstrepo.txt')
            else:       
                Utils.load_svngit(sys.argv[args['--file']+1])

            Utils.mkdir(NS.GIT_TEMP_DIR)
            Utils.mkdir(NS.SVN_TEMP_DIR)
            Utils.mkdir(NS.ABM_TEMP)
            Utils.printwf(str("Starting SVN GIT migration tool on %s" % datetime.datetime.now()))
            Utils.printwf("This may take a while... please wait...\r\n")
            mix = None
            workCnt = 0

            if args['--nohttps'] is not None:
                Utils.printwf("INFO: Will not use https but ssh")
                NS.NO_GIT_URI = True

            for entry in NS.GSvnGitMeta:
                
                depth = NS.GDepth          
                Utils.printwf("###############################################################")
                try:
                    tags = None
                    if 'tags' in entry: #tags are optional 
                       tags = entry['tags']
                    svn = entry['svn']
                    branch = entry['branch']
                    git = entry['git']
                    mix = SvnGitMixin(svnuri=svn, gituri=NS.CSI_GIT_URI, svnpath=None, gitpath=None, opt_tags=tags)
                    Utils.printwf(str("INFO: Cloning repos %s\t%s with branch %s" % (svn, git, branch)))                        
                    mix.git_clone(git, branch, NS.GDepth)
                    mix.svn_checkout()                    
                    mix.set_current("%s,%s,%s" % (svn, git, branch))
                    Utils.dump("---------------------------------------------------------------------------")
                    Utils.dump(str("INFO: %s,%s,%s" % (svn, git, branch)))
                    bDumpAll = False
                    tag_opt = -1
                    enable_tag_mode = False
                    if NS.GDEBUG is False:
                        if args['--update-db'] is not None:
                            NS.SVNGIT_UPDATE_DB_ONLY = True
                        if args['--abm'] is not None:
                            NS.SVNGIT_ON_ABM = True
                        if args['--dump-all'] is not None:
                            bDumpAll = True
                        if args['--tag'] is not None:
                            enable_tag_mode = True
                            try:
                                tag_opt = int(sys.argv[args['--tag']+1])
                            except:
                                Utils.printwf("ERROR: option [--tag] must be followed by mode (0, 1, 2)")
                                tag_opt = -1
                        
                        if args['--force'] is not None:
                            NS.BFORCE_ALL = True

                        if args['--untag'] is not None:
                            enable_tag_mode = True
                            tag_opt = 1
                        
                        if args['--retag'] is not None:
                            enable_tag_mode = True
                            tag_opt = 2

                        if args['--merge'] is not None:
                            mix.do_merge("{2019-01-01}", cleanup=clean)

                        elif args['--export-platforms'] is not None and GXml is not None:
                            Utils.printwf(str("Exporting xml data for: %s,%s,%s" % (svn, git, branch)))
                            mix.update_platforms()

                        elif args['--fullmerge'] is not None and enable_tag_mode is True:
                            mix.do_merge("{2019-01-01}", cleanup=clean)
                            _intag(mix, svn, git, branch, depth, tag_opt)

                        elif args['--fullmerge'] is not None and enable_tag_mode is False:
                            mix.do_merge("{2019-01-01}", cleanup=clean)
                            _intag(mix, svn, git, branch, depth, 0)
                            
                        elif args['--fullmerge'] is None and enable_tag_mode is True:
                            _intag(mix, svn, git, branch, depth, tag_opt) #tagonly

                        elif args['--purge-tags'] is not None:
                            mix.remove_tags()
                        else:
                            pass
                        _idump(mix, svn, git, branch, bDumpAll)
                    else:
                        #mix.do_merge("{2019-01-01}", cleanup=clean)
                        #_intag(mix, svn, git, branch, depth, 0)
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
    Utils.printwf("*************************************************************************************************")



#######################################################################################################################################
# todo:
# git rev-list -n 1 4_5_3_24 


