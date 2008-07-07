#!/usr/bin/env python2.4

'''Diagnostics Storage Ring EBPM Concentrator.'''

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
