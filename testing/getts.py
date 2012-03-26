#!/usr/bin/env dls-python2.6

from pkg_resources import require
require('cothread')
require('scipy')

import sys
import time
import numpy
from scipy.io import savemat

import cothread
from cothread.catools import *


count = int(sys.argv[1])
pvs = sys.argv[2:]

timestamps = numpy.zeros((count, len(pvs)))
arrivals = numpy.zeros((count, len(pvs)))
indices = numpy.zeros(len(pvs), dtype = int)
# We can prepare the results dictionary now because all of the entries are
# mutable values.
results = dict(
    indices = indices,
    timestamps = timestamps,
    arrivals = arrivals,
    pvs = pvs)

def on_update(value, index):
    now = time.time()
    n = indices[index]
    indices[index] += 1
    if n >= count:
        cothread.Quit()
    else:
        timestamps[n, index] = value.timestamp
        arrivals[n, index] = now

camonitor(pvs, on_update, format = FORMAT_TIME, all_updates = True)
cothread.WaitForQuit()
cothread.Sleep(0.5)

print indices

savemat('getts.mat', results, oned_as='row')
