

from common import *
from monitor import *


class InterlockReason: #(MonitorWaveform):
    def __init__(self):
        self.reason = MonitorWaveform('IL:REASON', initial_value=0,
            on_update = self.Update)

        self.x   = server.Create('IL:X', [0]*BPM_count)
        self.y   = server.Create('IL:Y', [0]*BPM_count)
        self.adc = server.Create('IL:ADC', [0]*BPM_count)

    def Update(self, updated):
#        if MonitorWaveform.Update(self, t):
        reason = self.reason.array.value
        self.x.update(reason & 1)
        self.y.update((reason & 2) >> 1)
        self.adc.update((reason & 0x18) != 0)


def ResetInterlock(pv, value):
    print 'Reset called', pv, value
    CaPutAll('IL:REASON', 0)
    return True

    
InterlockReason()
server.Create('IL:RESET', 0, ResetInterlock)

MonitorWaveform('IL:ENABLE_S', 'IL:ENABLE', initial_value=0)
