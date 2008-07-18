'''Management of beam current dependency.'''

import os.path
import numpy

import cothread
import builder

from config import *
from monitor import *
from updater import *



def LoadBCD(db, ma):
    '''Loads a BCD configuration file for the specified attenuation and
    current.'''
    filenames = [
        os.path.join(BCD_SourceDir, BCD_FileFormat % locals()) for xy in 'XY']
    return [numpy.array(map(float, file(filename).readlines()))
        for filename in filenames]
    


class AutoBCD:
    '''This class looks after the beam current dependency waveforms.'''
    
    def __init__(self):
        self.AutoBCD = builder.mbbOut('AUTOBCD',
            'Off', 'Zero', 'Auto', on_update = self.Update)
        self.status = Status('AUTOBCD')
        self.mode = 0
        
        cothread.Timer(1, self.UpdateStatus, retrigger = True)
        self.zero = numpy.zeros(BPM_count)
        self.db, self.ma = (22, 10)


    def UpdateBCD(self, target_X, target_Y):
        self.target_X = target_X
        self.target_Y = target_Y
        BcdXUpdater.WriteNewValue(target_X)
        BcdYUpdater.WriteNewValue(target_Y)


    def WriteNewValue(self, value):
        '''This is called when the attenuator value has changed.'''
        self.db, self.ma = value
        if self.mode == 2:
            self.Update_Auto()

    def AtTarget(self, value):
        return True
        

    # Updater routines
    def Update(self, value):
        try:
            action = self.Actions[int(value)]
        except:
            print pv, 'invalid value', value
            return False
        else:
            return action(self)

    def Update_Off(self):
        self.mode = 0
        return True
        
    def Update_Zero(self):
        self.mode = 1
        self.UpdateBCD(self.zero, self.zero)
        return True
        
    def Update_Auto(self):
        try:
            target_xy = LoadBCD(self.db, self.ma)
        except:
            print 'Unable to load BCD for %ddB/%dmA' % (self.db, self.ma)
            return False
        else:
            self.mode = 2
            self.UpdateBCD(*target_xy)
            return True


    def UpdateStatus(self):
        if self.mode == 0:
            self.status.Update(True)
        else:
            # In either of the BCD managed modes the status is only good if the
            # BCD target is our target and the BCD is at target.
            self.status.Update(
                BcdXUpdater.at_target and
                numpy.all(BcdXUpdater.writer.get() == self.target_X) and
                BcdYUpdater.at_target and
                numpy.all(BcdYUpdater.writer.get() == self.target_Y))

    Actions = [Update_Off, Update_Zero, Update_Auto]


class Attenuation(CrossUpdater):
    '''A control for managing the global attenuation setting together with the
    BCD setting.'''

    # Leave a delay between successive auto updates to give the system time
    # to respond.
    HOLDOFF = 5

    def write_change(self, name, min=0, max=100):
        def on_write(value):
            if min <= value <= max:
                setattr(self, name, value)
                return True
            else:
                return False
        return on_write
        
    
    def __init__(self, attenuations, auto_down, auto_up):
        self.auto_up = auto_up
        self.auto_down = auto_down

        builder.aOut('ATTENUATOR:UP', 0, 100,
            initial_value = auto_up,
            on_update = self.write_change('auto_up'))
        builder.aOut('ATTENUATOR:DOWN', 0, 100,
            initial_value = auto_down,
            on_update = self.write_change('auto_down'))
            
        
        # We directly control the ATTEN setting and BCD settings.
        updaters = (AttenUpdater, AutoBCD)
        values = [(db, (db, ma)) for db, ma in attenuations]
        enums = ['%ddB/%dmA' % (db, ma) for db, ma in attenuations] + ['Auto']

        self.auto_index = len(enums) - 1
        self.auto_mode = False
        self.holdoff = 0
        CrossUpdater.__init__(self,
            'ATTENUATION', updaters, values, enums)

        
    def UpdateSetting(self, index):
        # The special Auto mode is handle separately.
        self.auto_mode = index == self.auto_index
        if self.auto_mode:
            return True
        else:
            return CrossUpdater.UpdateSetting(self, index)


    def StepAttenuation(self, step):
        new_index = self.index + step
        if 0 <= new_index < self.auto_index and new_index != self.index:
            self.holdoff = self.HOLDOFF
            CrossUpdater.UpdateSetting(self, new_index)
            

    def UpdateMaxAdc(self, values):
        if self.holdoff:
            self.holdoff -= 1
        elif self.auto_mode:
            import enabled
            # We only pay any attention in auto mode
            # Only look at values from enabled BPMs
            mask = enabled.Health.get() == 0
            # Count the number of BPMs above the two AGC thresholds
            high_count    = \
                numpy.sum(numpy.where(mask, values > self.auto_up, 0))
            not_low_count = \
                numpy.sum(numpy.where(mask, values > self.auto_down, 0))

            # If enough BPMs are over the threshold we trigger a switch.
            if high_count >= 2:
                # If at least two BPMs are reading high then switch the
                # attenuation up one step.
                self.StepAttenuation(+1)
            elif not_low_count == 0:
                # If all of the BPMs are reading low, ie none are reading
                # above the low threshold, then switch the attenuation down
                # one step.
                self.StepAttenuation(-1)
        


AutoBCD = AutoBCD()

attenuation = Attenuation(ATTENUATOR_LIST, 10, 75)
