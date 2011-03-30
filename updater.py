# Interface for updating groups of PVs.

import numpy

import cothread
from softioc import builder

from bpm_list import *
from monitor import *


EnablerEnums = ['Disabled', 'Enabled']


class Status:
    def __init__(self, name):
        self.status = builder.boolIn(name + ':STAT',
            'Ok', 'Inconsistent',
            initial_value = 0)

    def Update(self, ok):
        if ok:
            self.status.set(0, severity=0)
        else:
            self.status.set(1, severity=2)
            

class Updater:
    '''An Updater(name, ...) instance manages a group of BPM PVs and
    provides the following published PVs:
    
        <name>_S        Writing to this PV writes to all BPMS
        <name>          A waveform monitoring the named value on all BPMs
        <name>:STAT     A status report field, Ok iff <name> == <name>_S

    Only <name>_S can be written to.
    '''
    
    def __init__(self, name, enums=(), min=0, max=1, waveform=False, **extras):

        assert not (enums and waveform), 'Can\'t specify waveform of enums'
        writer_name = name + '_S'

        self.monitor = MonitorWaveform(
            name + '_S', name, on_update = self.Update)

        if enums:
            min = 0
            max = len(enums) - 1
        self.name = name
        self.waveform = waveform
        self.min = min
        self.max = max
        self.at_target = False

        if waveform:
            self.writer = builder.WaveformOut(
                writer_name, initial_value = numpy.zeros(BPM_count),
                on_update = self.WriteNewValue, validate = self.Validate,
                **extras)
        elif enums:
            self.writer = builder.mbbOut(
                writer_name, initial_value = 0,
                on_update = self.WriteNewValue, validate = self.Validate,
                *enums, **extras)
        else:
            self.writer = builder.longOut(
                writer_name, initial_value = 0,
                on_update = self.WriteNewValue, validate = self.Validate,
                **extras)

        self.status = Status(name)

    def Validate(self, pv, value):
        '''Called asynchronously to validate the proposed new value.'''
        if numpy.amin(value) < self.min or self.max < numpy.amax(value):
            print pv.name, 'invalid value:', value
            return False
        elif self.waveform and numpy.shape(value) != (BPM_count,):
            # Check waveform is exactly the right size
            print pv.name, 'wrong array size:', numpy.shape(value)
            return False
        else:
            # If get here, passed all tests.
            return True

    def WriteNewValue(self, value):
        self.monitor.UpdateDefault(value)
        self.writer.set(value)
        CaPutAll(self.name + '_S', value)

    def Update(self, changed):
        self.at_target = (
            self.monitor.masked_value == self.writer.get()).all()
        self.status.Update(self.at_target)


    def AtTarget(self, value):
        return self.at_target and self.writer.get() == value

        

class CrossUpdater:
    '''A CrossUpdater(name, ...) instance manages a group of Updater instances.
    This is created by the following call:

    cross_updater = CrossUpdater(name, updaters, values, enums)

    The following PVs are published;

        <name>_S        This enumeration values to all controlled updaters
        <name>:STAT     Reports whether all controlled updaters are consistent

    The list of enums determines the enumerations in <name>_S, and values
    determines the values to be written each updater: value_list[i][j] is
    written to updaters[j] on setting enums[i].'''
    
    def __init__(self, name, pvlist, lookup, enums):
        builder.mbbOut(name + '_S', 
            initial_value = 0, on_update = self.UpdateSetting, *enums)
        self.status = Status(name)
        cothread.Timer(1, self.UpdateStatus, retrigger = True)

        self.lookup = lookup
        self.pvlist = pvlist
        self.index = 0
        self.setting = self.lookup[self.index]

    def UpdateSetting(self, index):
        try:
            self.setting = self.lookup[index]
            self.index = index
        except:
            print 'invalid value', index
            return False
        else:
            for pv, value in zip(self.pvlist, self.setting):
                pv.WriteNewValue(value)
            return True

    def UpdateStatus(self):
        self.status.Update(numpy.all([
            pv.AtTarget(value)
            for pv, value in zip(self.pvlist, self.setting)]))



Updater('CF:GOLDEN_X', waveform=True, min=-16, max=16, EGU='mm')
Updater('CF:GOLDEN_Y', waveform=True, min=-16, max=16, EGU='mm')
BcdXUpdater = Updater('CF:BCD_X', waveform=True, min=-16, max=16, EGU='mm')
BcdYUpdater = Updater('CF:BCD_Y', waveform=True, min=-16, max=16, EGU='mm')

Updater('FT:ENABLE', enums=EnablerEnums)
Updater('FR:ENABLE', enums=EnablerEnums)
Updater('BN:ENABLE', enums=EnablerEnums)

AutoswUpdater = Updater('CF:AUTOSW', enums=['Manual', 'Automatic'])
DscUpdater    = Updater('CF:DSC',
    enums=['Fixed gains', 'Unity gains', 'Automatic'])
AttenUpdater  = Updater('CF:ATTEN', min=0, max=62, EGU='dB')
DetuneUpdater = Updater('CK:DETUNE', min=-1000, max=1000, EGU='ticks')



CrossUpdater('MODE',
    (AutoswUpdater, DscUpdater, DetuneUpdater,),
    ((0, 0, 0), (1, 2, 400),),
    ('Tune', 'Orbit',))
