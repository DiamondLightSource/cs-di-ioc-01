"""Automatic current scaling.  Monitors the beam current reported by each"""

import cothread
from cothread import catools
from softioc import builder

import concentrator.config as config
import concentrator.maxadc as maxadc
import concentrator.monitor as monitor


class AutoCurrent:
    def __init__(self, interval):
        self.dcct = monitor.MonitorValue("SR-DI-DCCT-01:SIGNAL")
        self.scales = monitor.MonitorValue(monitor.BPMpvs("CF:ISCALE_S"))
        self.iir_k = builder.aOut(
            "ISCALE_K", 0, 1, initial_value=config.ISCALE_SCALING_K
        )
        self.threshold = builder.aOut(
            "ISCALE_MIN", 0, 250, initial_value=config.ISCALE_DCCT_THRESHOLD
        )

        self.timer = cothread.Timer(interval, self.Timer, retrigger=True)
        builder.aOut(
            "ISCALE_INTERVAL",
            0,
            120,
            initial_value=interval,
            on_update=self.UpdateInterval,
        )

    def UpdateInterval(self, interval):
        # The easiest way to change the timer interval is to cancel the timer
        # and fire a new one
        self.timer.cancel()
        self.timer = cothread.Timer(interval, self.Timer, retrigger=True)

    def Timer(self):
        dcct = self.dcct.value
        threshold = self.threshold.get()
        # Only do anything if the dcct reading is high enough
        if dcct > threshold:
            scales = self.scales.value
            currents = maxadc.current.waveform.value
            iir_k = self.iir_k.get()

            # Only adjust BPMs for which the ratio between observed and true
            # current is within a sensible range, say +- 10%
            current_ratio = dcct / currents
            sane_currents = (0.9 < current_ratio) & (current_ratio < 1.1)

            new_scales = scales * current_ratio
            iir_scales = iir_k * new_scales + (1 - iir_k) * scales
            pvs = [
                pv
                for pv, valid in zip(monitor.BPMpvs("CF:ISCALE_S"), sane_currents)
                if valid
            ]
            if pvs:
                ok = catools.caput(pvs, iir_scales[sane_currents], throw=False)


def setup(device_name="SR-DI-EBPM-01", interval=None):
    builder.SetDeviceName(device_name)
    if interval is None:
        interval = config.ISCALE_TIMER_INTERVAL
    return AutoCurrent(interval)
