#!/usr/bin/env python2.4

'''Diagnostics Storage Ring EBPM Concentrator.'''

import sys
DEBUG = 'D' in sys.argv[1:]
if DEBUG:
    sys.path.append('/scratch/local/python-debug')
    sys.path.append('/home/mga83/epics/cothread')
    sys.path.append('/home/mga83/epics/builder/build/lib')

    import cothread
    def Log(): print 'refs: %8d' % sys.gettotalrefcount()
    cothread.Timer(1, Log, retrigger = True)
else:
    from pkg_resources import require
    require('cothread==1.7')
    require('dls.builder==1.4')

import builder

builder.SetDeviceName('SR-DI-EBPM-01')

import enabled
import updater
import bcd
import maxadc
import interlock


from softioc import *

builder.LoadDatabase()
iocInit()
interactive_ioc(globals())
