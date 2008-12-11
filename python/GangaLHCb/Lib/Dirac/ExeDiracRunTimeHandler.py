#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#

from Ganga.GPIDev.Base import GangaObject
from Ganga.GPIDev.Adapters.IRuntimeHandler import IRuntimeHandler
from Ganga.GPIDev.Adapters.StandardJobConfig import StandardJobConfig
from DiracScript import DiracScript

import DiracShared

class ExeDiracRunTimeHandler(IRuntimeHandler):
    """The runtime handler to run plain executables on the Dirac backend"""

    def __init__(self):
        pass

    def master_prepare(self,app,appconfig):

        inputsandbox=app._getParent().inputsandbox[:]
        c = StandardJobConfig('',inputsandbox,[],[],None)
        return c

    def prepare(self,app,appconfig,appmasterconfig,jobmasterconfig):
        job = app.getJobObject()
        diracScript=DiracScript()
        c = StandardJobConfig(app.exe,[],app.args,
                              app._getParent().outputsandbox,app.env)
        logFile = 'GangaExcutable.log'
        diracScript.setExecutable(logFile=logFile,
                                  command=DiracShared.getGenericRunScript(job))
        diracScript.setName("Ganga_Executable")

        if job.inputdata:
            diracScript.inputdata([f.name for f in job.inputdata.files])
          
        if job.outputdata:
            diracScript.outputdata([f.name for f in job.outputdata.files])

        c.logfile=logFile
        c.script=diracScript
        
        return c

#\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\/\#
