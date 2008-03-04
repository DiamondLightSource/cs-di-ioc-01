from __future__ import division

from common import *
from monitor import *

import enabled
import bcd

MAX_ADC = 2**15

class MaxADC(MonitorWaveform):
    def __init__(self):
        MonitorWaveform.__init__(self,
            'SA:MAXADC', 'MAXADCWF', datatype = dbr_sts_long)

        self.maxadc = server.Create('MAXADC', 0, low=0, high=MAX_ADC)
        self.maxadc_pc = server.Create('MAXADC_PC',
            0.0, low=0, high=100, units='%', precision=1)
        
        self.severity = array([0]*BPM_count)

        self.maxid = server.Create('MAXADCID', '')


    def MonitorCallback(self, index, args):
        MonitorWaveform.MonitorCallback(self, index, args)
        self.severity[index] = args.dbr.severity

    def Update(self, t):
        MonitorWaveform.Update(self, t)

        maxsev = max(self.severity)
        maxval = max(self.array.value)
        maxval_pc = 100. * maxval / MAX_ADC
        self.maxadc.update(maxval, severity=maxsev)
        self.maxadc_pc.update(maxval_pc, severity=maxsev)

        self.maxid.update(BPMS[argmax(self.array.value)])

        bcd.attenuation.UpdateMaxAdc(100. * self.array.value / MAX_ADC)


class CurrentWaveform:
    def __init__(self):
        self.waveform = MonitorWaveform('SA:CURRENT', on_update = self.Update)

        self.mean = server.Create('SA:CURRENT:MEAN', 0.0,
            low = 0, high = 500, units = 'mA', precision = 3)

    def Update(self, t):
        active = enabled.ActiveArray(self.waveform.array.value)
        if active:
            self.mean.update(mean(active))


MaxADC()

from positions import BpmPositions
server.Create('SPOS', BpmPositions)

server.Create('BPMID', [1.1+i+0.1*j for i in range(24) for j in range(7)])

CurrentWaveform()
