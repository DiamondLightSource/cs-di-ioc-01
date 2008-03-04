'''Core EBPM monitoring code.  Monitors the SA positions and the ENABLED flags,
aggregating the result into a set of global health monitoring PVs.'''

from __future__ import division

from common import *
from monitor import *


Age = zeros(BPM_count)
Enabled = zeros(BPM_count)

EnabledList = arange(BPM_count)

# How far we will allow aging before reporting the BPM as unreachable.  We
# set this to four seconds to reduce the chance of spurious events.
#   Note that during EBPM machine clock synchronisation SA updates stop
# completely for about two seconds -- to avoid these causing spurious
# drop-outs the age limit is set quite high.
AGE_LIMIT = 20      # 4 seconds, 5 ticks per second


def WaveformDefaults(values, defaults):
    '''Sets all unreachable or disabled entries in values to the given
    defaults.'''
    return where(Health.value == 0, values, defaults)

def ActiveArray(values):
    '''Returns all the currently active entries.'''
    return take(values, EnabledList)


def EnabledCallback(index, value):
    Age[index] = 0
    Enabled[index] = value.value

    
def TimerTick(tick):
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
    NewHealth = where(Aged, 2, 1-Enabled)
    if NewHealth != Health.value:
        Health.value[:] = NewHealth
        Health.update()
        global EnabledList
        EnabledList = nonzero(NewHealth == 0)

    # Count the three possible health states
    EnabledCount.update(len(nonzero(NewHealth == 0)))
    DisabledCount.update(len(nonzero(NewHealth == 1)))
    UnreachableCount.update(len(nonzero(NewHealth == 2)))


class PositionWaveform(MonitorWaveform):
    def __Monitor(self, extra):
        return server.Create('%s:%s' % (self.name, extra), 0.0,
            low = -1.0, high = 1.0, precision = 5, units = 'mm')
        
    def __MonitorWF(self, extra):
        return server.Create('%s:%s' % (self.name, extra), [0.0]*BPM_count,
            low = -1.0, high = 1.0, precision = 5, units = 'mm')
        
    def __init__(self, name):
        MonitorWaveform.__init__(self, name, tick=0.1)

        self.std = self.__Monitor('STD')
        self.mean = self.__Monitor('MEAN')
        self.min = self.__Monitor('MIN')
        self.max = self.__Monitor('MAX')
        self.min_wf = self.__MonitorWF('MINWF')
        self.max_wf = self.__MonitorWF('MAXWF')

        self.reset = server.Create(
            '%s:RESET' % self.name, 0, self.ResetMinMax)

    def Update(self, t):
        MonitorWaveform.Update(self, t)

        active_array = ActiveArray(self.array.value)
        # Quick and dirty hack if nothing is live to ensure that none of the
        # array inspections routines below fail.
        if len(active_array) < 2:  active_array = array([0.0, 0.0])
        self.std.update(std(active_array))
        self.mean.update(mean(active_array))
        self.min.update(min(active_array))
        self.max.update(max(active_array))

        inactive_zero = array([0.0]*BPM_count)
        put(inactive_zero, EnabledList, active_array)
        self.min_wf.update(minimum(inactive_zero, self.min_wf.value))
        self.max_wf.update(maximum(inactive_zero, self.max_wf.value))

    def ResetMinMax(self, pv, value):
        active_array = ActiveArray(self.array.value)
        inactive_zero = array([0.0]*BPM_count)
        put(inactive_zero, EnabledList, active_array)
        self.min_wf.update(inactive_zero)
        self.max_wf.update(inactive_zero)
        return True



# We hook age reset code into the SA:X monitoring
class MonitorAgeReset(PositionWaveform):
    def MonitorCallback(self, index, args):
        PositionWaveform.MonitorCallback(self, index, args)
        Age[index] = 0

        

# For each IOC we record its health as one of the following values:
#
#   0 => Responding and enabled
#   1 => Responding and disabled
#   2 => Not responding (so disabled by default)
Health = server.Create('ENABLED', array([2] * BPM_count))
EnabledCount = server.Create('COUNT_ENABLED', 0)
DisabledCount = server.Create('COUNT_DISABLED', 0)
UnreachableCount = server.Create('COUNT_UNREACHABLE', 0)
server.Timer(0.2, TimerTick)

MonitorAgeReset('SA:X')
PositionWaveform('SA:Y')

MonitorArray('CF:ENABLED_S', EnabledCallback),
