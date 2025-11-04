from softioc import builder

import concentrator.monitor as monitor

builder.SetDeviceName("SR-DI-EBPM-01")
monitor.MonitorWaveform("IL:ENABLE_S", "IL:ENABLE")
