# SA updating DCCT waveforms.

from softioc import builder

import concentrator.bpm_list as bpm_list
import concentrator.intervals as intervals


class SA_Waveforms:
    sa_pvs = [("SA:X", 0), ("SA:Y", 0)]

    def __init__(self):
        pvs = [
            (intervals.Waveform_PV(pv, bpm_list.BPMpvs(pv)), shift)
            for pv, shift in self.sa_pvs
        ]
        self.controller = intervals.IntervalController(100, 100, pvs, self.on_update)

    def on_update(self, *args):
        pass


def setup(device_name="SR-DI-EBPM-01", create=False):
    builder.SetDeviceName(device_name)
    if create:
        return SA_Waveforms()
    return None
