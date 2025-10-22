'''Core EBPM monitoring code.  Monitors the SA positions and the ENABLED flags,
aggregating the result into a set of global health monitoring PVs.'''

from numpy import *

from softioc import builder, alarm
import cothread
from cothread import catools

from bpm_list import *
from monitor import *


# How far we will allow aging before reporting the BPM as unreachable.  We
# set this to four seconds to reduce the chance of spurious events.
#   Note that during EBPM machine clock synchronisation SA updates stop
# completely for about two seconds -- to avoid these causing spurious
# drop-outs the age limit is set quite high.
AGE_LIMIT = 20      # 4 seconds, 5 ticks per second

Age = ones(BPM_count, dtype=int) * AGE_LIMIT
Enabled = zeros(BPM_count)

EnabledList = nonzero(Enabled)

def WaveformDefaults(values, defaults):
    '''Sets all unreachable or disabled entries in values to the given
    defaults.'''
    return where(Health.get() == 0, values, defaults)

def ActiveArray(values):
    '''Returns all the currently active entries.'''
    return values[EnabledList]


def EnabledCallback(value, index):
    Age[index] = 0
    Enabled[index] = value


def TimerTick():
    # Age all the non responding entries and identify those which have passed
    # the age limit.
    global Age
    Age += 1
    Aged = Age > AGE_LIMIT
    # Prevent aging from growing indefinitely (though, in truth, this can run
    # for 13 years without overflow).
    Age = where(Aged, AGE_LIMIT, Age)

    # Now figure out whether an update is needed and if so, compute the new
    # health array.  The possible values are:
    #   2 => more than AGE_LIMIT ticks with no update: unreachable
    #   1 => marked as disabled
    #   0 => enabled and operating normally
    NewHealth = where(Aged, 2, 1 - Enabled)
    if (NewHealth != Health.get()).any():
        Health.set(NewHealth)
        global EnabledList
        EnabledList = nonzero(NewHealth == 0)

    # Count the three possible health states
    EnabledCount    .set(size(nonzero(NewHealth == 0)))
    DisabledCount   .set(size(nonzero(NewHealth == 1)))

    unreachable = size(nonzero(NewHealth == 2))
    if unreachable:
        unreachable_severity = alarm.MAJOR_ALARM
    else:
        unreachable_severity = alarm.NO_ALARM
    UnreachableCount.set(unreachable, severity = unreachable_severity)


class PositionWaveform(MonitorWaveform):
    def __Monitor(self, extra):
        return builder.aIn(
            '%s:%s' % (self.name, extra), -1, 1,
            PREC = 5,   EGU  = 'mm')

    def __MonitorWF(self, extra):
        return builder.Waveform(
            '%s:%s' % (self.name, extra), zeros(BPM_count),
            datatype = float32,
            LOPR = -1,  HOPR = 1,
            PREC = 5,   EGU  = 'mm')

    def __init__(self, name):
        MonitorWaveform.__init__(self, name, tick=0.1)

        self.std = self.__Monitor('STD')
        self.mean = self.__Monitor('MEAN')
        self.min = self.__Monitor('MIN')
        self.max = self.__Monitor('MAX')
        self.min_wf = self.__MonitorWF('MINWF')
        self.max_wf = self.__MonitorWF('MAXWF')

        self.reset = builder.Action(
            '%s:RESET' % self.name, on_update = self.ResetMinMax)

    def Update(self):
        MonitorWaveform.Update(self)

        active_array = self.active_value

        # Quick and dirty hack if nothing is live to ensure that none of the
        # array inspections routines below fail.
#         if len(active_array) < 2:  active_array = array([0.0, 0.0])
        if len(active_array) < 2:
            print('too small')
            return

        self.std.set(numpy.std(active_array))
        self.mean.set(mean(active_array))
        self.min.set(min(active_array))
        self.max.set(max(active_array))

        inactive_zero = array([0.0]*BPM_count)
        inactive_zero[EnabledList] = active_array
        self.min_wf.set(minimum(inactive_zero, self.min_wf.get()))
        self.max_wf.set(maximum(inactive_zero, self.max_wf.get()))

    def ResetMinMax(self, value):
        active_array = self.active_value
        inactive_zero = zeros(BPM_count)
        inactive_zero[EnabledList] = active_array
        self.min_wf.set(inactive_zero)
        self.max_wf.set(inactive_zero)
        return True



# We hook age reset code into the SA:X monitoring
class MonitorAgeReset(PositionWaveform):
    def MonitorCallback(self, value, index):
        PositionWaveform.MonitorCallback(self, value, index)
        Age[index] = 0



builder.SetDeviceName('SR-DI-EBPM-01')

# For each IOC we record its health as one of the following values:
#
#   0 => Responding and enabled
#   1 => Responding and disabled
#   2 => Not responding (so disabled by default)
Health = builder.Waveform('ENABLED', ones(BPM_count, dtype = int) * 2)
EnabledCount     = builder.aIn('COUNT_ENABLED',     initial_value = 0)
DisabledCount    = builder.aIn('COUNT_DISABLED',    initial_value = 0)
UnreachableCount = builder.aIn('COUNT_UNREACHABLE', initial_value = 0)
cothread.Timer(0.2, TimerTick, retrigger = True)

MonitorAgeReset('SA:X')
PositionWaveform('SA:Y')

MonitorArray('CF:ENABLED_S', EnabledCallback),
