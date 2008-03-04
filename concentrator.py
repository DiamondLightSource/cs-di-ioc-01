#!/usr/bin/env python2.4

'''Diagnostics Storage Ring EBPM Concentrator.'''

# First have to hack the path before importing pkg_resources (grr).
import sys, os
# if sys.argv[1] == 'D':
#     sys.path.append('/home/mga83/epics/cas/dist')
#     for module in ['ca/2-14', 'green/1-4']:
#         sys.path.append(os.path.join(
#             '/dls_sw/prod/common/python', module, 'dist'))

from pkg_resources import require
require('dls.ca2==2.14')
require('dls.cas==1.5')
require('dls.green==1.4')

import config
import enabled
import maxadc
import interlock
import updater
import bcd

import server

# if sys.argv[1] == 'D':
#     def ticker(t):
#         print sys.gettotalrefcount()
#     server.Timer(1, ticker)

server.RunServer()
