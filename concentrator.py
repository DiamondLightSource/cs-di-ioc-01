'''Diagnostics Storage Ring EBPM Concentrator.'''

import sys, os
from pkg_resources import require

require('cothread==2.6')
require('iocbuilder==3.23')

from softioc import builder, softioc

# A couple of identification PVs
builder.SetDeviceName('CS-DI-IOC-01')
builder.stringIn('WHOAMI', VAL = 'EBPM Concentrator')
builder.stringIn('HOSTNAME', VAL = os.uname()[1])

builder.SetDeviceName('SR-DI-EBPM-01')

from softioc import pvlog
import enabled
import updater
import bcd
import maxadc
import interlock
import autocurrent
import injection
import booster

builder.LoadDatabase()
softioc.iocInit()
softioc.interactive_ioc(globals())
