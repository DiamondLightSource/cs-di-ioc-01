# Concentrator waveforms for the booster and injection paths.


import numpy
from cothread import catools
from softioc import builder

import monitor
import updater


def BRpvs(name):
    return ['BR%02dC-DI-EBPM-%02d:%s' %
        (((2*n + 6) // 11) % 4 + 1, n + 1, name)
        for n in range(22)]

def LBpvs(name):
    return ['LB-DI-EBPM-%02d:%s' % (n + 1, name) for n in range(7)]

def BSpvs(name):
    return ['BS-DI-EBPM-%02d:%s' % (n + 1, name) for n in range(7)]


class BoosterWaveform(monitor.MonitorSimpleWaveform):
    def MonitorArray(self, name, callback, datatype=None, timestamps = False):
        if timestamps:
            format = catools.FORMAT_TIME
        else:
            format = catools.FORMAT_RAW
        return catools.camonitor(
            BRpvs(name), callback, datatype = datatype, format = format)

def BoosterCaPutAll(pv, value):
    monitor.CaPutAll(pv, value, make_pvs = BRpvs)

def BoosterUpdater(name, **kargs):
    return updater.Updater(name,
        monitor = BoosterWaveform, caputall = BoosterCaPutAll, **kargs)



builder.SetDeviceName('BR-DI-EBPM-01')

BoosterUpdater('CF:ATTEN', min = 0, max = 63, EGU = 'dB')
BoosterUpdater('CF:ATTEN:AGC', enums = ['AGC off', 'AGC on'])
BoosterUpdater('CF:AUTOSW', enums = ['Manual', 'Automatic'])
BoosterUpdater('CK:DETUNE', min = -1000, max = 1000, EGU = 'ticks')
for enable in ['FT', 'FR', 'BN', 'MS']:
    BoosterUpdater('%s:ENABLE' % enable, enums = ['Disabled', 'Enabled'])

builder.WaveformIn('BPMID', 1 + numpy.arange(22))
BoosterWaveform('SA:X')
BoosterWaveform('SA:Y')
BoosterWaveform('FT:X')
BoosterWaveform('FT:Y')
BoosterWaveform('FT:CHARGE')
