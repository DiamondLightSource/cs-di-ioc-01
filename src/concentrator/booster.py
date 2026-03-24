# Concentrator waveforms for the booster and injection paths.


import numpy
from cothread import catools
from softioc import builder

from . import monitor, updater


def br_pvs(name):
    return [
        f"BR{((2 * n + 6) // 11) % 4 + 1:02d}C-DI-EBPM-{n + 1:02d}:{name}"
        for n in range(22)
    ]


def lb_pvs(name):
    return [f"LB-DI-EBPM-{n + 1:02d}:{name}" for n in range(7)]


def bs_pvs(name):
    return [f"BS-DI-EBPM-{n + 1:02d}:{name}" for n in range(7)]


class BoosterWaveform(monitor.MonitorSimpleWaveform):
    def monitor_array(self, name, callback, datatype=None, timestamps=False):
        if timestamps:
            format = catools.FORMAT_TIME
        else:
            format = catools.FORMAT_RAW
        return catools.camonitor(
            br_pvs(name), callback, datatype=datatype, format=format
        )


def booster_ca_put_all(pv, value):
    monitor.ca_put_all(pv, value, make_pvs=br_pvs)


def booster_updater(name, **kargs):
    return updater.Updater(
        name, monitor=BoosterWaveform, caputall=booster_ca_put_all, **kargs
    )


def setup(device_name="BR-DI-EBPM-01"):
    builder.SetDeviceName(device_name)

    booster_updater("CF:ATTEN", min=0, max=63, EGU="dB")
    booster_updater("CF:ATTEN:AGC", enums=["AGC off", "AGC on"])
    booster_updater("CF:AUTOSW", enums=["Manual", "Automatic"])
    booster_updater("CF:DSC", enums=["Fixed gains", "Unity gains", "Automatic"])
    booster_updater("CK:DETUNE", min=-1000, max=1000, EGU="ticks")
    for enable in ["FT", "FR", "BN", "MS"]:
        booster_updater(f"{enable}:ENABLE", enums=["Disabled", "Enabled"])

    builder.WaveformIn("BPMID", 1 + numpy.arange(22))
    BoosterWaveform("SA:X")
    BoosterWaveform("SA:Y")
    BoosterWaveform("FT:X")
    BoosterWaveform("FT:Y")
    BoosterWaveform("FT:CHARGE")
