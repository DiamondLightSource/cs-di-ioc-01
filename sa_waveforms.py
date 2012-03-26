# SA updating DCCT waveforms.

from softioc import builder
import intervals
import bpm_list




class SA_Waveforms:

    sa_pvs = [
        ('SA:X',    0), ('SA:Y',    0)]

    def __init__(self):
        pvs = [
            (intervals.Waveform_PV(pv, bpm_list.BPMpvs(pv)), shift)
            for pv, shift in self.sa_pvs]
        self.controller = intervals.IntervalController(
            100, 100, pvs, self.on_update)

    def on_update(self, *args):
        pass


builder.SetDeviceName('SR-DI-EBPM-01')
# SA_Waveforms()
