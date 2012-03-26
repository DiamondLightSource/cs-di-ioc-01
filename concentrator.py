'''Diagnostics Storage Ring EBPM Concentrator.'''

import sys, os
DEBUG = 'D' in sys.argv[1:]
if DEBUG:
    print 'Running in debug mode'
    sys.path.append('/scratch/local/python-debug')
    sys.path.append('/home/mga83/epics/iocbuilder')
    sys.path.append('/home/mga83/epics/cothread')

    import cothread
    def Log(): print 'refs: %8d' % sys.gettotalrefcount()
    cothread.Timer(1, Log, retrigger = True)
else:
    from pkg_resources import require
    require('cothread==2.0')
    require('iocbuilder==3.18')

from softioc import builder, softioc

# A couple of identification PVs
builder.SetDeviceName('CS-DI-IOC-01')
builder.stringIn('WHOAMI', VAL = 'EBPM Concentrator')
builder.stringIn('HOSTNAME', VAL = os.uname()[1])

builder.SetDeviceName('SR-DI-EBPM-01')

import enabled
import updater
import bcd
import maxadc
import interlock
import autocurrent

builder.LoadDatabase()
softioc.iocInit()
softioc.interactive_ioc(globals())
