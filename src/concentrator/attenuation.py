"""Management of beam current dependency."""

import bisect

import cothread
import numpy
from softioc import builder

from concentrator.bpm_list import *
from concentrator.config import *
from concentrator.monitor import *
from concentrator.updater import *


class Attenuation:
    """A control for managing the global attenuation setting."""

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

        builder.aOut(
            "ATTENUATOR:UP",
            0,
            100,
            initial_value=auto_up,
            on_update=self.write_change("auto_up"),
        )
        builder.aOut(
            "ATTENUATOR:DOWN",
            0,
            100,
            initial_value=auto_down,
            on_update=self.write_change("auto_down"),
        )

        enums = ["%ddB/%dmA" % (db, ma) for db, ma in attenuations]
        mode = builder.mbbOut(
            "ATTENUATION_S",
            initial_value=0,
            on_update=self.UpdateSetting,
            *["Other"] + enums + ["Auto"],
        )

        self.status = Status("ATTENUATION")
        cothread.Timer(1, self.UpdateStatus, retrigger=True)

        self.atten = AttenUpdater
        self.atten_values = [db for db, ma in attenuations]
        self.auto_index = len(enums) + 1
        self.index = 0
        self.auto_mode = False
        self.holdoff = 0
        self.target_atten = None

        # Switch into auto mode after giving things time to settle
        cothread.Timer(6, lambda: mode.set(len(enums) + 1))

    def UpdateSetting(self, index):
        self.index = index
        # The special Auto mode is handled separately.
        self.auto_mode = index == self.auto_index
        if self.auto_mode:
            self.target_atten = self.atten.GetValue()
        elif 0 < index < self.auto_index:
            self.atten.WriteNewValue(self.atten_values[index - 1])
        return True

    def StepAttenuation(self, step):
        # Start by discovering the current attenuation.
        atten = self.atten.GetValue()
        index = bisect.bisect_left(self.atten_values, atten)
        if index < len(self.atten_values) and self.atten_values[index] == atten:
            # At the selected index
            new_index = index + step
        elif step > 0:
            new_index = index + step
        else:
            new_index = index

        if 0 <= new_index < len(self.atten_values):
            self.target_atten = self.atten_values[new_index]
            if self.target_atten != atten:
                print("StepAttenuation from", atten, "to", self.target_atten)
                self.holdoff = self.HOLDOFF
                self.atten.WriteNewValue(self.target_atten)

    def UpdateMaxAdc(self, values):
        if self.holdoff:
            self.holdoff -= 1
        elif self.auto_mode:
            import concentrator.enabled as enabled

            # We only pay any attention in auto mode
            # Only look at values from enabled BPMs
            health = enabled.Health.get()
            mask = health == 0
            # Count the number of BPMs above the two AGC thresholds
            high_count = numpy.sum(numpy.where(mask, values > self.auto_up, 0))
            not_low_count = numpy.sum(numpy.where(mask, values > self.auto_down, 0))
            unreachable_count = numpy.sum(health == 2)

            # If enough BPMs are over the threshold we trigger a switch.
            if high_count >= 2:
                # If at least two BPMs are reading high then switch the
                # attenuation up one step.
                self.StepAttenuation(+1)
            elif not_low_count == 0 and unreachable_count <= 2:
                # A trifle tricky here.  Only step attenuation down if no BPMs
                # are over the threshold and no more than two BPMs are recorded
                # as currently unreachable.
                self.StepAttenuation(-1)

    def UpdateStatus(self):
        """Ensures that the current attenuation readback is consistent with what
        we've configured."""
        if self.auto_mode:
            ok = self.atten.GetValue() == self.target_atten and self.atten.at_target
        elif self.index == 0:
            # In this mode we simply mirror ATTEN:STAT
            ok = self.atten.at_target
        else:
            # Specific attenuation selected, ensure this is where we are
            ok = self.atten.AtTarget(self.atten_values[self.index - 1])
        self.status.Update(ok)


builder.SetDeviceName("SR-DI-EBPM-01")
attenuation = Attenuation(ATTENUATOR_LIST, 10, 75)
