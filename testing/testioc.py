from pkg_resources import require

# require('cothread==2.2')
require('iocbuilder==3.23')

import sys
import os

sys.path.append('/home/mga83/epics/cothread')

from softioc import builder, softioc

sys.path.append('..')

# A couple of identification PVs
builder.SetDeviceName('CS-DI-IOC-01')
builder.stringIn('WHOAMI', VAL = 'EBPM Concentrator')
builder.stringIn('HOSTNAME', VAL = os.uname()[1])

import injection
import waveforms

builder.LoadDatabase()
softioc.iocInit()
softioc.interactive_ioc(globals())
