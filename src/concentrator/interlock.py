from softioc import builder

import concentrator.monitor as monitor


def setup(device_name="SR-DI-EBPM-01"):
    builder.SetDeviceName(device_name)
    monitor.MonitorWaveform("IL:ENABLE_S", "IL:ENABLE")
