#!/usr/bin/env python2.4

'''Diagnostics Storage Ring EBPM Concentrator.'''

import sys
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
    print require('numpy==1.1.0')
    print require('cothread==1.14')
    print require('iocbuilder==1.7')

import builder

builder.SetDeviceName('SR-DI-EBPM-01')

import enabled
import updater
import bcd
import maxadc
import interlock
import autocurrent


from softioc import *

builder.LoadDatabase()
iocInit()
interactive_ioc(globals())
