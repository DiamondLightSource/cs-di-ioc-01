import numpy
from softioc import builder

from . import config, enabled
from .bpm_list import BPMS, BPM_count, BPM_ids, BPM_name_id
from .monitor import MonitorSimpleWaveform, MonitorWaveform, monitor_array

MAX_ADC = 2**15

# Expose created instances after setup()
current = None
maxadc_instance = None


class MaxADC(MonitorWaveform):
    def __init__(self, on_maxadc_update=None):
        MonitorWaveform.__init__(self, "SA:MAXADC_PC", timestamps=True)

        self.maxadc = builder.aIn("MAXADC_PC", 0.0, 100, EGU="%", PREC=1)
        self.maxid = builder.stringIn("MAXADCID")

        # This PV now only exists for backwards compatibility -- the _PC PV has
        # the true readings.
        self.maxadc_raw = builder.longIn("MAXADC", 0, MAX_ADC)

        self.severity = numpy.zeros(BPM_count, dtype=int)
        self._on_maxadc_update = on_maxadc_update

    def monitor_callback(self, value, index):
        MonitorWaveform.monitor_callback(self, value, index)
        self.severity[index] = value.severity

    def update(self):
        MonitorWaveform.update(self)

        maxadcwf = self.masked_value
        maxsev = numpy.amax(self.severity)
        maxval = numpy.amax(maxadcwf)
        # Reconstruct (inferred) raw maximum ADC reading.  Only for backwards
        # compatibility -- historically this is the PV we archive.
        maxval_raw = int(round(MAX_ADC * maxval / 100.0))

        self.maxadc_raw.set(maxval_raw, severity=maxsev)
        self.maxadc.set(maxval, severity=maxsev)

        self.maxid.set(BPMS[numpy.argmax(maxadcwf)])

        # _on_maxadc_update is used for updating the attenuator
        if self._on_maxadc_update:
            self._on_maxadc_update(maxadcwf)


class CurrentWaveform:
    def __init__(self):
        invalid_bpms = [BPM_name_id[bpm] for bpm in config.BPMS_no_current]
        self.valid = numpy.ones(BPM_count, dtype=bool)
        self.valid[invalid_bpms] = False

        self.waveform = MonitorSimpleWaveform("SA:CURRENT", on_update=self.update)

        self.mean = builder.aIn("SA:CURRENT:MEAN", 0, 500, EGU="mA", PREC=3)

    def update(self, changed):
        # Select only the BPMs which are health and marked as valid.
        active = (enabled.Health.get() == 0) & self.valid
        values = self.waveform.value[active]
        if len(values) > 0:
            self.mean.set(numpy.mean(values))
        else:
            self.mean.set(0)


class CorrectorWaveform(MonitorSimpleWaveform):
    def corrector_pvs(self, name):
        return [f"SR{c + 1:02d}A-CS-FOFB-01:{name}" for c in range(24)]

    def monitor_array(self, *args, **kwargs):
        return monitor_array(*args, pvs=self.corrector_pvs, **kwargs)


def setup(device_name="SR-DI-EBPM-01", on_maxadc_update=None):
    """Register MaxADC and related waveforms. Returns dict with instances."""
    global current, maxadc_instance

    builder.SetDeviceName(device_name)

    maxadc_instance = MaxADC(on_maxadc_update=on_maxadc_update)
    builder.WaveformIn("BPMID", list(BPM_ids))

    current = CurrentWaveform()

    # Postmortem statistics
    MonitorWaveform("PM:X_OFL", tick=1, datatype=numpy.uint8)
    MonitorWaveform("PM:Y_OFL", tick=1, datatype=numpy.uint8)
    MonitorWaveform("PM:ADC_OFL", tick=1, datatype=numpy.uint8)

    MonitorWaveform("PM:X_OFFSET", tick=1, datatype=int, offset=15384)
    MonitorWaveform("PM:Y_OFFSET", tick=1, datatype=int, offset=15384)
    MonitorWaveform("PM:ADC_OFFSET", tick=1, datatype=int, offset=15384)

    # Interlocks
    MonitorSimpleWaveform("IL:MINX", tick=1)
    MonitorSimpleWaveform("IL:MAXX", tick=1)
    MonitorSimpleWaveform("IL:MINY", tick=1)
    MonitorSimpleWaveform("IL:MAXY", tick=1)

    # Communication controller statistics
    MonitorSimpleWaveform("FF:PROCESS_TIME_US", tick=1)
    MonitorSimpleWaveform("FF:RXFIFO", tick=1)
    MonitorSimpleWaveform("FF:TXFIFO", tick=1)
    MonitorSimpleWaveform("FF:SOFT_ERR", tick=1)
    MonitorSimpleWaveform("FF:HARD_ERR", tick=1)
    MonitorSimpleWaveform("FF:FRAME_ERR", tick=1)
    MonitorSimpleWaveform("FF:BPM_COUNT", tick=1)

    # Corrector waveforms
    builder.SetDeviceName("SR-CS-FOFB-01")
    builder.WaveformIn("CELLID", 1 + numpy.arange(24))
    CorrectorWaveform("TFMAX", tick=1)
    CorrectorWaveform("TFMIN", tick=1)
    CorrectorWaveform("NODES", tick=1)

    return {"current": current, "maxadc": maxadc_instance}
