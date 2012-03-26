'''Management of beam current dependency.'''

import os.path
import numpy

import cothread
from softioc import builder

from config import *
from bpm_list import *
from monitor import *
from updater import *



class Attenuation(CrossUpdater):
    '''A control for managing the global attenuation setting.'''

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

        # We directly control the ATTEN setting
        updaters = (AttenUpdater,)
        values = [(db, (db, ma)) for db, ma in attenuations]
        enums = ['%ddB/%dmA' % (db, ma) for db, ma in attenuations] + ['Auto']

        self.auto_index = len(enums) - 1
        self.auto_mode = False
        self.holdoff = 0
        CrossUpdater.__init__(self, 'ATTENUATION', updaters, values, enums)


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


attenuation = Attenuation(ATTENUATOR_LIST, 10, 75)
