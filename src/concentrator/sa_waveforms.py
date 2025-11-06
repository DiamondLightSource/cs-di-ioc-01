# SA updating DCCT waveforms.

from softioc import builder

from . import bpm_list, intervals


class SAWaveforms:
    sa_pvs = [("SA:X", 0), ("SA:Y", 0)]

    def __init__(self):
        pvs = [
            (intervals.WaveformPV(pv, bpm_list.bpm_pvs(pv)), shift)
            for pv, shift in self.sa_pvs
        ]
        self.controller = intervals.IntervalController(100, 100, pvs, self.on_update)

    def on_update(self, *args):
        pass


def setup(device_name="SR-DI-EBPM-01", create=False):
    builder.SetDeviceName(device_name)
    if create:
        return SAWaveforms()
    return None
