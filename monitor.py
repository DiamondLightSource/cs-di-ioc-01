from __future__ import division

from common import *

from dls.ca2 import catools
import dls.green as green

import enabled


# Converts a BPM specific PV into one PV per BPM.
def BPMpvs(name):
    return ['%s:%s' % (bpm, name) for bpm in BPMS]



def CaPutAll(pv, value, put_array=False):
    if not put_array:
        value = [value]*BPM_count
    
    '''Performs a background block caput to all BPM PVs with name pv.  Any
    errors are merely logged to the console.'''
    def Greenlet():
        # green.co_sleep(1) spawn now queues the greenlet create request so
        # will sleep 1 tick anyway

        # What about timeouts here?  Does this timeout block other
        # processing?  Doesn't seem to!
        sl = catools.caput(
            BPMpvs(pv), value, timeout = 5, throw = False)
#         sl_fail = [s for s in sl if s != catools.ECA_NORMAL]
#         if sl_fail:
#             print 'CaPutAll', pv, value, '->', sl_fail

    # Run the entire put process in the background.
    green.spawn(Greenlet)


def MonitorArray(name, callback, datatype=None):
    return [
        catools.camonitor(pv,
            lambda value, index=n: callback(index, value),
            flags = catools.DBE_VALUE | catools.DBE_ALARM,
            datatype = datatype)
        for n, pv in enumerate(BPMpvs(name))]
    


class MonitorWaveform:
    '''The MonitorWaveform class is the basic building block for monitoring an
    array of PVs, one per BPM.  The PV value read from each BPM is written into
    self.array.
    '''
    def __init__(self,
            name, server_name=None, tick=0.2, datatype=None,
            initial_value=0.0, default_value=None,
            on_update=None):

        if server_name is None:     server_name = name
        if default_value is None:   default_value = initial_value

        self.name = name
        self.default_value = default_value
        self.on_update = on_update

        # We maintain two copies of the reported values: the values actually
        # received from the BPM, and the value reported to the IOC server.
        # The difference is that the reported value is corrected for
        # unreachable BPMs by replacing stale values with defaults -- but we
        # need to hang onto the reported values in case the BPM becomes
        # reachable again.
        self.value = array([initial_value]*BPM_count)
        self.array = server.Create(server_name, [initial_value]*BPM_count)
        
        self.monitors = MonitorArray(name, self.MonitorCallback, datatype)
        self.changed = False

        server.Timer(tick, self.Update)

    def MonitorCallback(self, index, args):
        '''This routine is called each time any of the monitored elements
        changes.'''
        self.value[index] = args.dbr.value[0]
        self.changed = True

    def UpdateDefault(self, default_value):
        self.default_value = default_value
        self.changed = True

    def Update(self, t):
        '''This is called on a timer and is used to generate a collected update
        for the entire waveform.'''
        # For all those BPMs which are unresponsive we substitute the current
        # default value
        new_value = enabled.WaveformDefaults(self.value, self.default_value)
        changed = sometrue(new_value != self.array.value)
        if changed:
            self.array.update(new_value)
        if self.on_update:
            self.on_update(changed)


__all__ = ['CaPutAll', 'MonitorArray', 'MonitorWaveform']
