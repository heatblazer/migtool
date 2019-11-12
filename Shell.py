import os
import subprocess 
import sys

class Cmd(object):
    """ spawn a new process and capture stdout and stderr"""

    def __init__(self, cmstr=None, verbose=False):
        self._cmstr = cmstr
        self._out = None
        self._err = None
        self._dataout = []
        self._dataerr = []
        self.pro = None
        self._vmode = verbose


    def __call__(self):
        if self._cmstr is not None:
            self.execute(self._cmstr)


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


    def sys_exec(self, cmd):
        return os.system(cmd)


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
