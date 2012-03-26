
from softioc import builder
import intervals
import bpm_list


# class MaskedWaveform(intervals.Waveform_PV):
#     def __init__(self, name, mask, shift = 0):
#         # The mask is a mutable value which is managed externally
#         self.mask = mask
# 
#         pvs = ['%s:%s' % (bpm, name) for bpm in bpm_list.BPMS]
#         self.__super.__init__(name, pvs, shift = shift)
# 
#         N = len(pvs)
#         self.wf_raw = builder.Waveform('%s:RAW' % name, length = N)
#         self.wf_out = intervals.Waveform_Out(name, N)
#         self.wf_ts = intervals.Waveform_TS('%s:TS' % name, '%s:AGE' % name, N)
# 
#     def on_update(self, value):
#         self.wf_raw.on_update(value)
#         self.wf_out.on_update(value)
#         self.wf_ts.on_update(value)
#         self.__super.on_update(value)


builder.SetDeviceName('SR-DI-EBPM-01')

# Postmortem PVs.
pm_pvs = [
    'PM:X_OFL',     'PM:Y_OFL',     'PM:ADC_OFL',
    'PM:X_OFFSET',  'PM:Y_OFFSET',  'PM:ADC_OFFSET']
intervals.TriggeredController(500,
    [(intervals.Waveform_Out(pv, bpm_list.BPMpvs(pv)), 0)
     for pv in pm_pvs])
