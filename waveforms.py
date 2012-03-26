import numpy

from softioc import builder
import intervals
import bpm_list




def MakeWaveforms(pvs, offset = 0):
    return [(intervals.MaskedWaveform(
        pv, bpm_list.BPMpvs(pv), [enabled_mask, 0], offset), 0)
        for pv in pvs]


enabled_mask = numpy.ones(bpm_list.BPM_count, dtype = bool)

builder.SetDeviceName('SR-DI-EBPM-01')

# Postmortem PVs: PM:{ADC,X,Y}_OFFSET
#   Triggered on postmortem event.
#   OFFSET values need to be adjusted by fudge factor before being published.
intervals.TriggeredController(500,
    MakeWaveforms([
        'PM:X_OFFSET',  'PM:Y_OFFSET',  'PM:ADC_OFFSET'], offset = 15384))


# SA PVs
#   SA:{MAXADC,CURRENT,X,Y}
#   Triggered at 10 Hz by EBPM
sa_controller = intervals.IntervalController(101, 100,
    MakeWaveforms(['SA:X', 'SA:Y', 'SA:MAXADC', 'SA:CURRENT']),
    history_length = 3)
intervals.Controller_extra('SA', sa_controller)
