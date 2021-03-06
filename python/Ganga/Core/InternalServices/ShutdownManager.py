##########################################################################
# Ganga - a computational task management tool for easy access to Grid resources
# http://cern.ch/ganga
#
# $Id: ShutdownManager.py,v 1.1 2008-07-17 16:40:50 moscicki Exp $
#
# Copyright (C) 2003-2007 The Ganga Project
#
# This file is part of Ganga.
#
# Ganga is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Ganga is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
##########################################################################
"""
Extend the behaviour of the default *atexit* module to support:

 1) automatically catching of the (possible) exceptions thrown by exit function
 
 2) exit function prioritization (lower value means higher priority) 
  E.g:
    import atexit
    atexit.register((<PRIORITY>,myfunc),args)  
   
  The backward-compatibility is kept so the existing code using :
    import atexit
    atexit.register(myfunc,args)
  registers the function with the lowest priority (sys.maxint)
"""

import atexit

from Ganga.Utility.logging import getLogger
logger = getLogger()


def _ganga_run_exitfuncs():
    """run any registered exit functions

    atexit._exithandlers is traversed based on the priority.
    If no priority was registered for a given function
    than the lowest priority is assumed (LIFO policy)

    We keep the same functionality as in *atexit* bare module but
    we run each exit handler inside a try..catch block to be sure all
    the registered handlers are executed
    """

    # Set the disk timeout to 1 sec, sacrifice stability for quick-er exit
    from Ganga.Utility.Config import setConfigOption
    setConfigOption('Configuration', 'DiskIOTimeout', 1)

    try:
        from Ganga.GPI import queues
        queues.lock()
    except Exception, err:
        logger.debug("This should only happen if Ganga filed to initialize correctly")

    ## Stop the Mon loop from iterating further!
    from Ganga.Core import monitoring_component
    if monitoring_component is not None:
        monitoring_component.disableMonitoring()

    ## This will stop the Registries flat but we may still have threads processing data!
    #from Ganga.Core.InternalServices import Coordinator
    #if Coordinator.servicesEnabled:
    #    Coordinator.disableInternalServices( shutdown = True )

    # Set the disk timeout to 3 sec, sacrifice stability for quick-er exit
    #from Ganga.Utility.Config import setConfigOption
    #setConfigOption('Configuration', 'DiskIOTimeout', 3)

    from Ganga.Core.MonitoringComponent.Local_GangaMC_Service import _purge_actions_queue, stop_and_free_thread_pool
    _purge_actions_queue()
    stop_and_free_thread_pool()

    try:
        from Ganga.GPI import queues
        queues._purge_all()
    except Exception, err:
        logger.debug("This should only happen if Ganga filed to initialize correctly")

    def priority_cmp(f1, f2):
        """
        Sort the exit functions based on priority in reversed order
        """
        # extract the priority number from the function element
        p1 = f1[0][0]
        p2 = f2[0][0]
        # sort in reversed order
        return cmp(p2, p1)

    def add_priority(x):
        """
        add a default priority to the functions not defining one (default priority=sys.maxint)
        return a list containg ((priority,func),*targs,*kargs) elements
        """
        import sys
        func = x[0]
        if isinstance(func, tuple) and len(x[0]) == 2:
            return x
        else:
            new = [(sys.maxsize, func)]
            new.extend(x[1:])
            return new

    atexit._exithandlers = map(add_priority, atexit._exithandlers)
    atexit._exithandlers.sort(priority_cmp)

    import inspect
    while atexit._exithandlers:

        (priority, func), targs, kargs = atexit._exithandlers.pop()
        try:
            if hasattr(func, 'im_class'):
                for cls in inspect.getmro(func.__self__.__class__):
                    if func.__name__ in cls.__dict__:
                        logger.debug(cls.__name__ + " : " + func.__name__)
            else:
                logger.debug("noclass : " + func.__name__)
            func(*targs, **kargs)
        except Exception as x:
            s = 'Cannot run one of the exit handlers: %s ... Cause: %s' % (func.__name__, str(x))
            logger.warning(s)

    logger.debug("Shutting Down Repository_runtime")
    from Ganga.Runtime import Repository_runtime
    Repository_runtime.shutdown()

    import Ganga.Utility.logging
    if Ganga.Utility.logging.requires_shutdown is True:
        Ganga.Utility.logging.shutdown()

    from Ganga.Core.InternalServices import Coordinator
    Coordinator.servicesEnabled = False

    from Ganga.Core.GangaRepository.SessionLock import removeGlobalSessionFiles, removeGlobalSessionFileHandlers
    removeGlobalSessionFileHandlers()
    removeGlobalSessionFiles()

    from Ganga.Runtime import bootstrap
    if bootstrap.DEBUGFILES or bootstrap.MONITOR_FILES:
        bootstrap.printOpenFiles()


def install():
    """
    Install a new shutdown manager, by overriding methods from atexit module
    """
    # override the atexit exit function
    atexit._run_exitfuncs = _ganga_run_exitfuncs
    #del atexit

    # override the default exit function
    import sys
    sys.exitfunc = atexit._run_exitfuncs

#
#$Log: not supported by cvs2svn $
# Revision 1.2  2007/07/27 14:31:56  moscicki
# credential and clean shutdown updates from Adrian (from Ganga-4-4-0-dev-branch)
#
# Revision 1.1.2.2  2007/07/27 13:03:17  amuraru
#*** empty log message ***
#
#
