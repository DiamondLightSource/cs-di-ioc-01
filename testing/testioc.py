from pkg_resources import require

require('cothread==2.6')
require('iocbuilder==3.23')

import sys
import os

from softioc import builder, softioc

sys.path.append('..')

# A couple of identification PVs
builder.SetDeviceName('CS-DI-IOC-01')
builder.stringIn('WHOAMI', initial_val = 'EBPM Concentrator')
builder.stringIn('HOSTNAME', initial_val = os.uname()[1])

import injection
import waveforms

builder.LoadDatabase()
softioc.iocInit()
softioc.interactive_ioc(globals())
