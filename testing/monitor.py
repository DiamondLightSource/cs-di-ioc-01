#!/usr/bin/env dls-python3

import os
import sys

port = '6064'
if sys.argv[1:]:
    port = sys.argv[1]
os.environ['EPICS_CA_SERVER_PORT'] = port

import time
import numpy
import cothread
from cothread.catools import *
from cothread import dbr


class MaxWf:
    def __init__(self, pv, update):
        self.update = update
        camonitor(pv, self.wf_update)

    def wf_update(self, value):
        max_val = dbr.ca_float(numpy.max(value))
        max_val.name = value.name
        self.update(max_val)

class BinWf:
    def __init__(self, pv, update):
        self.update = update
        camonitor(pv, self.wf_update)

    def wf_update(self, value):
        result = 0
        for v in value:
            result = (result << 1) + bool(v)
        self.update(result)


S_PER_DAY = 3600 * 24   # Seconds per day
UNIX_EPOCH = 719529     # Unix epoch in Matlab time

class Gather:
    def __init__(self, length):
        self.values = numpy.zeros(length)

    def update(self, index, action = None):
        def do_update(value):
            self.values[index] = value
            if action:
                action()
        return do_update

    def show(self):
        now = time.time()
        matlab_time = now / S_PER_DAY + UNIX_EPOCH
        print matlab_time,
        for value in self.values:
            print value,
        print
        self.values[:] = 0


gather = Gather(4)

MaxWf('SR-DI-EBPM-01:MS:DELTAI:AGE', gather.update(0))
MaxWf('CS-DI-XFER-01:INJECT:AGE', gather.update(1))
BinWf('CS-DI-XFER-01:INJECT:VALID', gather.update(2))
camonitor('CS-DI-XFER-01:INJECT:DELAY', gather.update(3, action = gather.show))


cothread.WaitForQuit()
