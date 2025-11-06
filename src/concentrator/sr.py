# Concentrator waveforms for the storage ring

from softioc import builder

from . import monitor, updater


def evr_pvs(name):
    return [f"SR{c + 1:02d}C-DI-EVR-01:{name}" for c in range(24)]


class EVRWaveform(monitor.MonitorSimpleWaveform):
    def monitor_array(self, *args, **kwargs):
        return monitor.monitor_array(*args, pvs=evr_pvs, **kwargs)


def evr_ca_put_all(pv, value):
    monitor.ca_put_all(pv, value, make_pvs=evr_pvs)


def evr_updater(name, monitor_name=None, **kargs):
    if monitor_name is None:
        monitor_name = name
    return updater.Updater(
        name,
        monitor=EVRWaveform,
        caputall=evr_ca_put_all,
        monitor_name=monitor_name,
        **kargs,
    )


def setup(device_name="SR-DI-EVR-01"):
    builder.SetDeviceName(device_name)
    evr_updater(
        "TRIG:MODE", enums=["", "Normal", "Synchronised", "Triggered", "Extra Trigger"]
    )
    evr_updater("OT2D", "SET_HW.OT2D", max=0)
