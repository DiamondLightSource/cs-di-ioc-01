# Concentrator waveforms for the storage ring

import numpy
from cothread import catools
from softioc import builder

import monitor
import updater


def EVRpvs(name):
    return ['SR%02dC-DI-EVR-01:%s' % (c+1, name) for c in range(24)]

class EVRWaveform(monitor.MonitorSimpleWaveform):
    def MonitorArray(self, *args, **kwargs):
        return monitor.MonitorArray(*args, pvs = EVRpvs, **kwargs)

def EVRCaPutAll(pv, value):
    monitor.CaPutAll(pv, value, make_pvs = EVRpvs)

def EVRUpdater(name, monitor_name = None, **kargs):
    if monitor_name is None:
        monitor_name = name
    return updater.Updater(name,
        monitor = EVRWaveform, caputall = EVRCaPutAll,
        monitor_name = monitor_name,
        **kargs)

builder.SetDeviceName('SR-DI-EVR-01')

EVRUpdater('TRIG:MODE',
    enums = ['', 'Normal', 'Synchronised', 'Triggered', 'Extra Trigger'])
EVRUpdater('OT2D', 'SET_HW.OT2D', max = 0)
