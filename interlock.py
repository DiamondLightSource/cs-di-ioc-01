import numpy
from softioc import builder
from monitor import *

class InterlockReason: #(MonitorWaveform):
    def __init__(self):
        self.reason = MonitorWaveform('IL:REASON',
            on_update = self.Update, datatype = int)

        zero = numpy.zeros(BPM_count, dtype = int) 
        self.x   = builder.Waveform('IL:X', zero)
        self.y   = builder.Waveform('IL:Y', zero)
        self.adc = builder.Waveform('IL:ADC', zero)

    def Update(self, changed):
#        if MonitorWaveform.Update(self, t):
        reason = self.reason.masked_value
        self.x.set(reason & 1)
        self.y.set((reason & 2) >> 1)
        self.adc.set((reason & 0x18) != 0)


def ResetInterlock(value):
    CaPutAll('IL:REASON', 0)

    
InterlockReason()
builder.Action('IL:RESET', on_update = ResetInterlock)

MonitorWaveform('IL:ENABLE_S', 'IL:ENABLE')
