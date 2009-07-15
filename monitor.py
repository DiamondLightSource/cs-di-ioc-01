import numpy

import builder
import cothread

from cothread import catools 

__all__ = ['CaPutAll',
    'MonitorArray', 'MonitorValue',
    'MonitorWaveform', 'MonitorSimpleWaveform',
    'BPM_count', 'BPMS']



# List of all BPMs in the storage ring.
BPMS = ['SR%02dC-DI-EBPM-%02d' % (c+1, n+1)
    for c in range(24) for n in range(7)]
BPM_count = len(BPMS)

# Converts a BPM specific PV into one PV per BPM.
def BPMpvs(name):
    return ['%s:%s' % (bpm, name) for bpm in BPMS]



def CaPutAll(pv, value):
    '''Writes a value to all PVs.  The write process is spawned in the
    background to avoid blocking any other activites.'''
    ok = catools.caput(BPMpvs(pv), value, throw = False)
    if not numpy.all(ok):
        print 'caput failed:'
        for result in ok:
            if not result:
                print '   ', result.name, '-', str(result)
                break       # for the moment...


def MonitorArray(name, callback, datatype=None, timestamps = False):
    if timestamps:
        format = catools.FORMAT_TIME
    else:
        format = catools.FORMAT_RAW
    return catools.camonitor(
        BPMpvs(name), callback,
        events = catools.DBE_VALUE | catools.DBE_ALARM,
        datatype = datatype, format = format)

    
class MonitorValue:
    def __init__(self, names, datatype=None, **kargs):
        if isinstance(names, str):
            self.value = 0
            update = self.update_scalar
        else:
            self.value = numpy.zeros(len(names), dtype = datatype)
            update = self.update_vector
        catools.camonitor(names, update, datatype = datatype, **kargs)

    def update_scalar(self, value):
        self.value = value

    def update_vector(self, value, index):
        self.value[index] = value
        


class MonitorSimpleWaveform:
    def __init__(self,
            name, server_name=None, tick=0.2, datatype=None,
            on_update=None, timestamps=False):

        if server_name is None:
            server_name = name

        self.on_update = on_update

        self.value = numpy.zeros(BPM_count, dtype = datatype)
        self.waveform = builder.Waveform(
            server_name, +self.value, datatype = datatype)
        
        MonitorArray(name, self.MonitorCallback,
            datatype = datatype, timestamps = timestamps)
        cothread.Timer(tick, self.Update, retrigger=True)

    def MonitorCallback(self, value, index):
        '''This routine is called each time any of the monitored elements
        changes.'''
        self.value[index] = value

    def Update(self):
        '''This is called on a timer and is used to generate a collected update
        for the entire waveform.'''
        self.waveform.set(+self.value)
        if self.on_update:
            self.on_update()

            
class MonitorWaveform:
    '''The MonitorWaveform class is the basic building block for monitoring an
    array of PVs, one per BPM.  The PV value read from each BPM is written into
    self.array.
    '''
    
    def __init__(self,
            name, server_name=None, tick=0.2, datatype=None,
            default_value=None,
            on_update=None, timestamps=False, offset=None):

        if server_name is None:     server_name = name
        if default_value is None:   default_value = 0

        self.name = name
        self.default_value = default_value
        self.on_update = on_update
        self.offset = offset

        # We maintain two copies of the reported values: the values actually
        # received from the BPM, and the value reported to the IOC server.
        # The difference is that the reported value is corrected for
        # unreachable BPMs by replacing stale values with defaults -- but we
        # need to hang onto the reported values in case the BPM becomes
        # reachable again.
        self.raw_value = numpy.zeros(BPM_count, dtype = datatype)
        self.waveform = builder.Waveform(
            server_name, +self.raw_value, datatype = datatype)
        
        self.changed = False
        MonitorArray(name, self.MonitorCallback,
            datatype = datatype, timestamps = timestamps)
        cothread.Timer(tick, self.Update, retrigger=True)

    def MonitorCallback(self, value, index):
        '''This routine is called each time any of the monitored elements
        changes.'''
        self.raw_value[index] = value
        self.changed = True

    def UpdateDefault(self, default_value):
        self.default_value = default_value
        self.changed = True

    def Update(self):
        '''This is called on a timer and is used to generate a collected update
        for the entire waveform.'''
        # For all those BPMs which are unresponsive we substitute the current
        # default value
        import enabled
        new_value = enabled.WaveformDefaults(
            self.raw_value, self.default_value)
        if self.offset:
            new_value -= self.offset
        
        changed = (new_value != self.masked_value).any()
        if changed:
            self.waveform.set(+new_value)
        if self.on_update:
            self.on_update(changed)

    @property
    def masked_value(self):
        '''Returns the masked value as presented to the outside.  This is
        distinct from the raw value as received from BPMs.'''
        return self.waveform.get()

    @property
    def active_value(self):
        '''Returns the subset of "active" values: rather than defaulting
        disabled values, in this version they are removed from the array.
        This means that the active_value array may be any length <= 168.'''
        import enabled
        return enabled.ActiveArray(self.raw_value)
