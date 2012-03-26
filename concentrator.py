'''Diagnostics Storage Ring EBPM Concentrator.'''

import sys, os
from pkg_resources import require

require('cothread==2.1')
require('iocbuilder==3.20')

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
