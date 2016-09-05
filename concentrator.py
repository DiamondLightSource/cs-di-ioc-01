'''Diagnostics Storage Ring EBPM Concentrator.'''

import sys, os
from pkg_resources import require

require('cothread==2.13')
require('numpy==1.11.1')
require('epicsdbbuilder==1.1')

from softioc import builder, softioc

# A couple of identification PVs
builder.SetDeviceName('CS-DI-IOC-01')
builder.stringIn('WHOAMI', VAL = 'Diagnostics Concentrator')
builder.stringIn('HOSTNAME', VAL = os.uname()[1])

builder.Action('RESTART', on_update = softioc.epicsExit)


from softioc import pvlog

import enabled
import updater
import attenuation
import maxadc
import interlock
import autocurrent
import bcd
import injection
import booster
import sr

builder.LoadDatabase()
softioc.iocInit()
softioc.interactive_ioc(globals())
