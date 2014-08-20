'''Diagnostics Storage Ring EBPM Concentrator.'''

import sys, os
from pkg_resources import require

require('cothread==2.10')
require('iocbuilder==3.45')

from softioc import builder, softioc

# A couple of identification PVs
builder.SetDeviceName('CS-DI-IOC-01')
builder.stringIn('WHOAMI', VAL = 'Diagnostics Concentrator')
builder.stringIn('HOSTNAME', VAL = os.uname()[1])


from softioc import pvlog

import enabled
import updater
import attenuation
import maxadc
import interlock
import autocurrent
import injection
import booster

builder.LoadDatabase()
softioc.iocInit()
softioc.interactive_ioc(globals())
