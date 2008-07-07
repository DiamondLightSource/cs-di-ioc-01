import numpy

import builder

from monitor import *
from positions import BpmPositions
import enabled
import bcd


MAX_ADC = 2**15

class MaxADC(MonitorWaveform):
    def __init__(self):
        MonitorWaveform.__init__(self, 'SA:MAXADC', 'MAXADCWF',
            datatype = int, timestamps = True)

        self.maxadc = builder.longIn('MAXADC', 0, MAX_ADC)
        self.maxadc_pc = builder.aIn('MAXADC_PC',
            0.0, 100, EGU = '%', PREC = 1)
        self.maxid = builder.stringIn('MAXADCID')
        
        self.severity = numpy.zeros(BPM_count, dtype = int)


    def MonitorCallback(self, value, index):
        MonitorWaveform.MonitorCallback(self, value, index)
        self.severity[index] = value.severity

    def Update(self):
        MonitorWaveform.Update(self)

        maxsev = numpy.amax(self.severity)
        maxval = numpy.amax(self.value)
        maxval_pc = 100. * maxval / MAX_ADC
        self.maxadc.set(maxval, severity=maxsev)
        self.maxadc_pc.set(maxval_pc, severity=maxsev)

        self.maxid.set(BPMS[numpy.argmax(self.value)])

        bcd.attenuation.UpdateMaxAdc(100. * self.value / MAX_ADC)


class CurrentWaveform:
    def __init__(self):
        self.waveform = MonitorWaveform('SA:CURRENT', on_update = self.Update)

        self.mean = builder.aIn('SA:CURRENT:MEAN', 
            0, 500, EGU = 'mA', PREC = 3)

    def Update(self, t):
        active = enabled.ActiveArray(self.waveform.value)
        if len(active) > 0:
            self.mean.set(numpy.mean(active))


MaxADC()

builder.WaveformIn('SPOS', BpmPositions)
builder.WaveformIn('BPMID',
    [1.1+i+0.1*j for i in range(24) for j in range(7)])

CurrentWaveform()
