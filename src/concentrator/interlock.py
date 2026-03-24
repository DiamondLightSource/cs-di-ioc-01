from softioc import builder

from . import monitor


def setup(device_name="SR-DI-EBPM-01"):
    builder.SetDeviceName(device_name)
    monitor.MonitorWaveform("IL:ENABLE_S", "IL:ENABLE")
