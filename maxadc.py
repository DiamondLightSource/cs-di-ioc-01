import numpy

from softioc import builder

from monitor import *
from positions import BpmPositions
import enabled
import bcd
import config


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

        maxadcwf = self.masked_value
        maxsev = numpy.amax(self.severity)
        maxval = numpy.amax(maxadcwf)
        maxval_pc = 100. * maxval / MAX_ADC
        self.maxadc.set(maxval, severity=maxsev)
        self.maxadc_pc.set(maxval_pc, severity=maxsev)

        self.maxid.set(BPMS[numpy.argmax(maxadcwf)])

        bcd.attenuation.UpdateMaxAdc(100. * maxadcwf / MAX_ADC)


class CurrentWaveform:
    def __init__(self):
        invalid_bpms = [7*(c-1) + n-1 for c, n in config.BPMS_no_current]
        self.valid = numpy.ones(BPM_count, dtype=bool)
        self.valid[invalid_bpms] = False
        
        self.waveform = MonitorSimpleWaveform('SA:CURRENT',
            on_update = self.Update)

        self.mean = builder.aIn('SA:CURRENT:MEAN', 
            0, 500, EGU = 'mA', PREC = 3)

    def Update(self):
        # Select only the BPMs which are health and marked as valid.
        active = (enabled.Health.get() == 0) & self.valid
        values = self.waveform.value[active]
        if len(values) > 0:
            self.mean.set(numpy.mean(values))
        else:
            self.mean.set(0)


MaxADC()

builder.WaveformIn('SPOS', BpmPositions)
builder.WaveformIn('BPMID', BPM_ids)

current = CurrentWaveform()


# Free running deviation statistics
MonitorWaveform('FR:STDX', tick = 0.2)
MonitorWaveform('FR:PPX',  tick = 0.2)
MonitorWaveform('FR:STDY', tick = 0.2)
MonitorWaveform('FR:PPY',  tick = 0.2)

# Postmortem statistics
MonitorWaveform('PM:X_OFL',      tick = 1, datatype = bool)
MonitorWaveform('PM:Y_OFL',      tick = 1, datatype = bool)
MonitorWaveform('PM:ADC_OFL',    tick = 1, datatype = bool)

MonitorWaveform('PM:X_OFFSET',   tick = 1, datatype = int, offset = 15384)
MonitorWaveform('PM:Y_OFFSET',   tick = 1, datatype = int, offset = 15384)
MonitorWaveform('PM:ADC_OFFSET', tick = 1, datatype = int, offset = 15384)
