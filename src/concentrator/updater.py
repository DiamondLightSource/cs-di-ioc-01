# Interface for updating groups of PVs.

import cothread
import numpy
from softioc import builder

from . import config
from .monitor import MonitorSimpleWaveform, MonitorWaveform, ca_put_all

EnablerEnums = ["Disabled", "Enabled"]


class Status:
    def __init__(self, name):
        self.status = builder.boolIn(
            name + ":STAT", "Ok", "Inconsistent", initial_value=0
        )

    def update(self, ok):
        if ok:
            self.status.set(0, severity=0)
        else:
            self.status.set(1, severity=2)


class Updater:
    """An Updater(name, ...) instance manages a group of BPM PVs and
    provides the following published PVs:

        <name>_S        Writing to this PV writes to all BPMS
        <name>          A waveform monitoring the named value on all BPMs
        <name>:STAT     A status report field, Ok iff <name> == <name>_S

    Only <name>_S can be written to.
    """

    def __init__(
        self,
        name,
        enums=(),
        min=0,
        max=1,
        waveform=False,
        monitor: type[MonitorWaveform] | type[MonitorSimpleWaveform] = MonitorWaveform,
        caputall=ca_put_all,
        auto_set=True,
        monitor_name=None,
        **extras,
    ):
        assert not (enums and waveform), "Can't specify waveform of enums"
        writer_name = name + "_S"
        if monitor_name is None:
            monitor_name = writer_name

        self.caputall = caputall
        self.monitor = monitor(monitor_name, name, on_update=self.update)

        if enums:
            min = 0
            max = len(enums) - 1
        self.name = name
        self.monitor_name = monitor_name
        self.waveform = waveform
        self.min = min
        self.max = max
        self.at_target_flag = False
        self.length = self.monitor.length

        if waveform:
            self.writer = builder.WaveformOut(
                writer_name,
                initial_value=numpy.zeros(self.length),
                on_update=self.write_new_value,
                validate=self.validate,
                **extras,
            )
        elif enums:
            self.writer = builder.mbbOut(
                writer_name,
                *enums,
                initial_value=0,
                on_update=self.write_new_value,
                validate=self.validate,
                **extras,
            )
        else:
            self.writer = builder.longOut(
                writer_name,
                initial_value=0,
                on_update=self.write_new_value,
                validate=self.validate,
                **extras,
            )

        self.status = Status(name)

        if auto_set:
            cothread.Timer(5, self.on_startup)

    def validate(self, pv, value):
        """Called asynchronously to validate the proposed new value."""
        if self.min < self.max and (
            numpy.amin(value) < self.min or self.max < numpy.amax(value)
        ):
            print(pv.name, "invalid value:", value)
            return False
        elif self.waveform and numpy.shape(value) != (self.length,):
            # Check waveform is exactly the right size
            print(pv.name, "wrong array size:", numpy.shape(value))
            return False
        else:
            # If get here, passed all tests.
            return True

    def write_new_value(self, value):
        self.monitor.update_default(value)
        if self.waveform:
            self.writer.set(value)
        else:  # mmbOut or longOut which must be integer type
            self.writer.set(int(value))
        self.caputall(self.monitor_name, value)

    def update(self, changed):
        self.at_target_flag = (self.monitor.masked_value == self.writer.get()).all()
        self.status.update(self.at_target_flag)

    def at_target(self, value):
        return self.at_target_flag and self.writer.get() == value

    def get_value(self):
        """Returns consensus value."""
        active = self.monitor.active_value
        if len(active) == 0:
            raise ValueError(
                f"{self.name}: no active BPMs, cannot determine consensus value"
            )
        return numpy.median(active)

    # Called during startup after things have had a moment to settle
    def on_startup(self):
        val = self.get_value()
        if self.waveform:
            self.writer.set(val)
        else:  # mmbOut or longOut which must be integer type
            self.writer.set(int(val))
        self.update(False)


class CrossUpdater:
    """A CrossUpdater(name, ...) instance manages a group of Updater instances.
    This is created by the following call:

    cross_updater = CrossUpdater(name, updaters, values, enums)

    The following PVs are published;

        <name>_S        This enumeration values to all controlled updaters
        <name>:STAT     Reports whether all controlled updaters are consistent

    The list of enums determines the enumerations in <name>_S, and values
    determines the values to be written each updater: value_list[i][j] is
    written to updaters[j] on setting enums[i]."""

    def __init__(self, name, pvlist, lookup, enums, initial_value=0):
        builder.mbbOut(
            name + "_S",
            *enums,
            initial_value=initial_value,
            on_update=self.update_setting,
        )
        self.status = Status(name)
        cothread.Timer(1, self.update_status, retrigger=True)

        self.lookup = lookup
        self.pvlist = pvlist
        self.index = initial_value
        self.setting = self.lookup[self.index]

    def update_setting(self, index):
        try:
            self.setting = self.lookup[index]
            self.index = index
        except Exception:
            print("invalid value", index)
            return False
        else:
            for pv, value in zip(self.pvlist, self.setting, strict=True):
                pv.write_new_value(value)
            return True

    def update_status(self):
        self.status.update(
            numpy.all(
                [
                    pv.at_target(value)
                    for pv, value in zip(self.pvlist, self.setting, strict=True)
                ]
            )
        )


def reset_bcd(value):
    ca_put_all("BCD_X_S", 0)
    ca_put_all("BCD_Y_S", 0)


def setup(device_name="SR-DI-EBPM-01"):
    """Register the common updater PVs and return key updater instances."""
    builder.SetDeviceName(device_name)

    builder.boolOut("RESET_BCD", on_update=reset_bcd)

    MonitorSimpleWaveform("CF:GOLDEN_X_S")
    MonitorSimpleWaveform("CF:GOLDEN_Y_S")
    MonitorSimpleWaveform("CF:BCD_X_S")
    MonitorSimpleWaveform("CF:BCD_Y_S")

    Updater("FT:ENABLE", enums=EnablerEnums)
    Updater("FR:ENABLE", enums=EnablerEnums)
    Updater("BN:ENABLE", enums=EnablerEnums)

    autosw = Updater("CF:AUTOSW", enums=["Manual", "Automatic"])
    dsc = Updater("CF:DSC", enums=["Fixed gains", "Unity gains", "Automatic"])
    atten = Updater("CF:ATTEN", min=0, max=62, EGU="dB")
    detune = Updater("CK:DETUNE", min=-1000, max=1000, EGU="ticks")

    CrossUpdater(
        "MODE",
        (
            autosw,
            dsc,
            detune,
        ),
        (
            (0, 0, 0),
            (1, 2, config.ORBIT_DETUNE),
        ),
        (
            "Tune",
            "Orbit",
        ),
        initial_value=1,
    )

    return {
        "AutoswUpdater": autosw,
        "DscUpdater": dsc,
        "AttenUpdater": atten,
        "DetuneUpdater": detune,
    }
