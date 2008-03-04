from common import *
from monitor import *

import enabled


EnablerEnums = ['Disabled', 'Enabled']


class Status:
    def __init__(self, name):
        self.status = server.Create(name + ':STAT', 0,
            enums = ['Ok', 'Inconsistent'])

    def Update(self, ok):
        if ok:
            self.status.update(0, severity=0)
        else:
            self.status.update(1, severity=2)

class Updater:
    '''An Updater(name, ...) instance manages a group of BPM PVs and
    provides the following published PVs:
    
        <name>_S        Writing to this PV writes to all BPMS
        <name>          A waveform monitoring the named value on all BPMs
        <name>:STAT     A status report field, Ok iff <name> == <name>_S

    Only <name>_S can be written to.
    '''
    
    def __init__(self, name,
            waveform=False, datatype=None, initial_value=None,
            enums=None, min=0, max=1, **extras):

        if initial_value is None:
            if enums:
                initial_value = 0
                min = 0
                max = len(enums) - 1
            else:
                initial_value = 0.0

        self.monitor = MonitorWaveform(name + '_S', name,
            datatype=datatype,
            initial_value=initial_value,
            on_update = self.Update)

        self.name = name
        self.waveform = waveform
        self.min = min
        self.max = max
        self.at_target = False
        
        if waveform:
            initial_value = [initial_value]*BPM_count
        self.writer = server.Create(name + '_S',
            initial_value, self.WriteNewValue, enums=enums, **extras)

        self.status = Status(name)

    def WriteNewValue(self, pv, value):
        if self.min <= min(value) and max(value) <= self.max:
            if self.waveform:
                # Check waveform is exactly the right size
                if shape(value) != (BPM_count,):
                    print pv.name, 'wrong array size:', shape(value)
                    return False
            else:
                value = value[0]
                
            self.monitor.UpdateDefault(value)
            CaPutAll(self.name + '_S', value, put_array=self.waveform)
            self.writer.update(value)
            return True
        else:
            print pv.name, 'invalid value:', value
            return False

    def Update(self, changed):
        self.at_target = alltrue(self.monitor.array.value == self.writer.value)
        self.status.Update(self.at_target)


    def AtTarget(self, value):
        return self.at_target and self.writer.value == value

        

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
        server.Create(name + '_S', 0, self.UpdateSetting, enums=enums)
        self.status = Status(name)
        server.Timer(1, self.UpdateStatus)

        self.lookup = lookup
        self.pvlist = pvlist
        self.index = 0
        self.setting = self.lookup[self.index]

    def UpdateSetting(self, p, value):
        try:
            index = int(value)
            self.setting = self.lookup[index]
            self.index = index
        except:
            print p, 'invalid value', value
            return False
        else:
            for pv, value in zip(self.pvlist, self.setting):
                pv.WriteNewValue(pv, array([value]))
            return True

    def UpdateStatus(self, tick):
        self.status.Update(alltrue([
            pv.AtTarget(value)
            for pv, value in zip(self.pvlist, self.setting)]))



Updater('CF:GOLDEN_X', waveform=True, min=-16, max=16, units='mm')
Updater('CF:GOLDEN_Y', waveform=True, min=-16, max=16, units='mm')
BcdXUpdater = Updater('CF:BCD_X', waveform=True, min=-16, max=16, units='mm')
BcdYUpdater = Updater('CF:BCD_Y', waveform=True, min=-16, max=16, units='mm')

Updater('FT:ENABLE', enums=EnablerEnums)
Updater('FR:ENABLE', enums=EnablerEnums)
Updater('BN:ENABLE', enums=EnablerEnums)

AutoswUpdater = Updater('CF:AUTOSW', enums=['Manual', 'Automatic'])
DscUpdater    = Updater('CF:DSC',
    enums=['Fixed gains', 'Unity gains', 'Automatic'])
AttenUpdater  = Updater('CF:ATTEN',
    initial_value=0, min=0, max=62, units='dB')
DetuneUpdater = Updater('CK:DETUNE',
    initial_value=0, min=-1000, max=1000, units='ticks')



CrossUpdater('MODE',
    (AutoswUpdater, DscUpdater, DetuneUpdater,),
    ((0, 0, 0), (1, 2, 400),),
    ('Tune', 'Orbit',))
