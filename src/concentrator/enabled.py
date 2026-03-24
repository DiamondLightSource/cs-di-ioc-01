"""Core EBPM monitoring code.  Monitors the SA positions and the ENABLED flags,
aggregating the result into a set of global health monitoring PVs."""

from typing import Any

import cothread
import numpy as np
from softioc import alarm, builder

from .bpm_list import BPM_count
from .monitor import MonitorWaveform, monitor_array

# How far we will allow aging before reporting the BPM as unreachable.  We
# set this to four seconds to reduce the chance of spurious events.
#   Note that during EBPM machine clock synchronisation SA updates stop
# completely for about two seconds -- to avoid these causing spurious
# drop-outs the age limit is set quite high.
AGE_LIMIT = 20  # 4 seconds, 5 ticks per second

Age = np.ones(BPM_count, dtype=int) * AGE_LIMIT
Enabled = np.zeros(BPM_count)

EnabledList = np.nonzero(Enabled)


def waveform_defaults(values, defaults):
    """Sets all unreachable or disabled entries in values to the given
    defaults."""
    return np.where(Health.get() == 0, values, defaults)


def active_array(values):
    """Returns all the currently active entries."""
    return values[EnabledList]


def enabled_callback(value, index):
    Age[index] = 0
    Enabled[index] = value


def timer_tick():
    # Age all the non responding entries and identify those which have passed
    # the age limit.
    global Age
    Age += 1
    aged = Age > AGE_LIMIT
    # Prevent aging from growing indefinitely (though, in truth, this can run
    # for 13 years without overflow).
    Age = np.where(aged, AGE_LIMIT, Age)

    # Now figure out whether an update is needed and if so, compute the new
    # health array.  The possible values are:
    #   2 => more than AGE_LIMIT ticks with no update: unreachable
    #   1 => marked as disabled
    #   0 => enabled and operating normally
    new_health = np.where(aged, 2, 1 - Enabled)
    if (new_health != Health.get()).any():
        Health.set(new_health)
        global EnabledList
        EnabledList = np.nonzero(new_health == 0)

    # Count the three possible health states
    EnabledCount.set(np.size(np.nonzero(new_health == 0)))
    DisabledCount.set(np.size(np.nonzero(new_health == 1)))

    unreachable = np.size(np.nonzero(new_health == 2))
    if unreachable:
        unreachable_severity = alarm.MAJOR_ALARM
    else:
        unreachable_severity = alarm.NO_ALARM
    UnreachableCount.set(unreachable, severity=unreachable_severity)


class PositionWaveform(MonitorWaveform):
    def __monitor(self, extra):
        return builder.aIn(f"{self.name}:{extra}", -1, 1, PREC=5, EGU="mm")

    def __monitor_wf(self, extra):
        return builder.Waveform(
            f"{self.name}:{extra}",
            np.zeros(BPM_count),
            datatype=np.float32,
            LOPR=-1,
            HOPR=1,
            PREC=5,
            EGU="mm",
        )

    def __init__(self, name):
        MonitorWaveform.__init__(self, name, tick=0.1)

        self.std = self.__monitor("STD")
        self.mean = self.__monitor("MEAN")
        self.min = self.__monitor("MIN")
        self.max = self.__monitor("MAX")
        self.min_wf = self.__monitor_wf("MINWF")
        self.max_wf = self.__monitor_wf("MAXWF")
        self.reset = builder.Action(f"{self.name}:RESET", on_update=self.reset_min_max)

    def update(self):
        MonitorWaveform.update(self)

        active_array = self.active_value

        # If nothing is live ensure that the array inspections routines below don't fail
        if len(active_array) < 2:
            return

        self.std.set(np.std(active_array))
        self.mean.set(np.mean(active_array))
        self.min.set(np.min(active_array))
        self.max.set(np.max(active_array))

        inactive_zero = np.array([0.0] * BPM_count)
        inactive_zero[EnabledList] = active_array
        self.min_wf.set(np.minimum(inactive_zero, self.min_wf.get()))
        self.max_wf.set(np.maximum(inactive_zero, self.max_wf.get()))

    def reset_min_max(self, value):
        active_array = self.active_value
        inactive_zero = np.zeros(BPM_count)
        inactive_zero[EnabledList] = active_array
        self.min_wf.set(inactive_zero)
        self.max_wf.set(inactive_zero)
        return True


# We hook age reset code into the SA:X monitoring
class MonitorAgeReset(PositionWaveform):
    def monitor_callback(self, value, index):
        PositionWaveform.monitor_callback(self, value, index)
        Age[index] = 0


# Placeholders until setup() is called
Health: Any = None
EnabledCount: Any = None
DisabledCount: Any = None
UnreachableCount: Any = None


def setup(device_name="SR-DI-EBPM-01"):
    """Create Health PVs, timers and monitors."""
    global Health, EnabledCount, DisabledCount, UnreachableCount

    builder.SetDeviceName(device_name)

    # For each IOC we record its health as one of the following values:
    #
    #   0 => Responding and enabled
    #   1 => Responding and disabled
    #   2 => Not responding (so disabled by default)
    Health = builder.Waveform("ENABLED", np.ones(BPM_count, dtype=int) * 2)
    EnabledCount = builder.aIn("COUNT_ENABLED", initial_value=0)
    DisabledCount = builder.aIn("COUNT_DISABLED", initial_value=0)
    UnreachableCount = builder.aIn("COUNT_UNREACHABLE", initial_value=0)
    cothread.Timer(0.2, timer_tick, retrigger=True)

    MonitorAgeReset("SA:X")
    PositionWaveform("SA:Y")

    (monitor_array("CF:ENABLED_S", enabled_callback),)
