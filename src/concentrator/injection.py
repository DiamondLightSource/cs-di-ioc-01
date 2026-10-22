# PVs for injection calculation.

import numpy
from softioc import builder

from . import bpm_list, config, intervals

SR_BUNCHES = 936  # 561.6 m
SR_MA_TO_NC = 1e6 * SR_BUNCHES / config.F_RF  # 1.87 us (534 kHz)


class MSWaveform(intervals.WaveformOut):
    ms_pvs = [f"{bpm}:MS:DELTAI" for bpm in bpm_list.BPMS]
    HISTORY = 3

    def __init__(self):
        super().__init__("MS:DELTAI", self.ms_pvs)
        self.mean_pv = builder.aIn("MS:DELTAI:MEAN", TSE=-2)

        # All the code below and most of the code in on_update() is in place to
        # cope with glitches in MS:DELTAI and to try and prevent them from
        # contributing to MS:DELTAI:MEAN.
        #
        # When we see a glitch we blank updates from this source for three
        # updates, so we maintain a history for this.
        self.glitch_history = numpy.zeros((self.HISTORY, len(self.ms_pvs)), dtype=bool)

    def on_update(self, value):
        super().on_update(value)

        # Identify glitches by finding updates that are beyond the glitch threshold,
        # also ignore values with no update on this tick
        glitches = (abs(value.value) > config.GLITCH_THRESHOLD) | ~value.valid_wf

        # If there are too few values which havnt glitched abandon the entire update
        if (~glitches).sum() < config.MIN_VALID_DELTAI_VALUES:
            glitches[:] = True

        # Add any detected glitches to the glitch history
        self.glitch_history = numpy.roll(self.glitch_history, 1, 0)
        self.glitch_history[0] = glitches

        # Exclude glitches and invalid values from our mean calculation
        mean_mask = value.valid_wf & ~self.glitch_history.any(0)
        valid_values = value.value[mean_mask]

        # Finally compute the mean using the glitch free values. If we have no
        # valid values this will return NaN
        value.mean = numpy.mean(valid_values)
        self.mean_pv.set(value.mean, timestamp=value.timestamp)


class TransferRatio:
    """Manages transfer ratio for a single pair of values."""

    def __init__(self, name, input, output, threshold, low, lolo=None):
        self.name = name
        self.input = input
        self.output = output
        self.low = low
        if lolo is None:
            lolo = 0.5 * low
        self.lolo = lolo
        self.threshold = threshold
        self.pv = builder.aIn(name, 0, 100, PREC=2, EGU="%", TSE=-2)

    def on_update(self, timestamp, values, valid):
        if valid[self.input] and valid[self.output]:
            input = values[self.input]
            output = values[self.output]

            if input > self.threshold:
                xfer = 100.0 * output / input
                if xfer > self.low:
                    severity = 0
                elif xfer > self.lolo:
                    severity = 1
                else:
                    severity = 2
            else:
                xfer = 0
                severity = 0
        else:
            # If either input or output values are invalid
            # force an INVALID state
            xfer = 0
            severity = 3

        self.pv.set(xfer, timestamp=timestamp, severity=severity)


class History:
    """Historical waveforms with remembered validity.  As for TransferRatio, we
    pick up the values from waveforms passed in"""

    def __init__(self, length, index):
        self.index = index
        self.history = numpy.zeros(length)
        self.valid = numpy.zeros(length, dtype=bool)

    def add(self, values, valid):
        self.history = numpy.roll(self.history, -1)
        self.valid = numpy.roll(self.valid, -1)
        self.history[-1] = values[self.index]
        self.valid[-1] = valid[self.index]

    def mean(self, length):
        data = self.history[-length:][self.valid[-length:]]
        if len(data) > 0:
            return data.mean()
        else:
            return 0


class Transfer:
    """Transfer efficiency calculation"""

    xfr_pvs = [
        ("LB-DI-ICT-01:SIGNAL", 0),  # 0
        ("LB-DI-ICT-02:SIGNAL", 0),  # 1
        ("LB-DI-ICT-03:SIGNAL", 200),  # 2
        ("BR01C-DI-DCCT-01:CHARGE", 200),  # 3
        ("BS-DI-ICT-01:SIGNAL", 99),  # 4
        ("BS-DI-ICT-02:SIGNAL", 99),  # 5
        ("SR23C-DI-DCCT-01:SIGNAL", 200),  # 6
    ]

    SR_SIGNAL = 6
    MS_CHARGE = 7

    acceptance = 0.5

    def __init__(self):
        # The MS waveform is an EBPM derived waveform
        builder.SetDeviceName("SR-DI-EBPM-01")
        ms_wf = (MSWaveform(), 303.8)

        # Transfer efficiency PVs.  These are all CS-DI-XFER-01 PVs
        builder.SetDeviceName("CS-DI-XFER-01")

        # We gather injection transfer data from the LB and BS ICTs, from the
        # booster and storage ring DCCTs, and from the EBPM MS records.  The SR
        # DCCT needs to be converted into an SR:CHARGE calculation by scaling
        # and taking differences, and the MS values need to be scaled to compute
        # MS:DELTAQ
        pvs = [(intervals.ValuePV(pv), shift) for pv, shift in self.xfr_pvs] + [ms_wf]
        self.controller = intervals.IntervalController(
            200, 400, pvs, self.on_update, history_length=3
        )

        # Generate visible status PVs for the controller.
        self.extra = intervals.ControllerExtra("INJECT", self.controller)
        # This will be updated with the scaled charge from MS
        self.dq_pv = builder.aIn("MS:DELTAQ", 0, 1, PREC=3, EGU="nC", TSE=-2)
        self.inject_pv = builder.Waveform(
            "INJECT:VALUES", numpy.zeros(len(pvs)), TSE=-2
        )

        # Storage ring delta current turned into an injection charge together
        # with the associated control variables
        self.charge_pv = builder.aIn("SR:CHARGE", 0, 1, PREC=3, EGU="nC", TSE=-2)
        self.last_signal_valid = False
        self.last_signal = numpy.nan

        # Transfer efficiencies calculated as offsets into gathered interval
        # data using offets:
        #   LB ICT 01   0       LB ICT 02   1       LB ICT 03   2
        #   BR DCCT     3       BS ICT 01   4       BS ICT 02   5
        #   SR DCCT     6       MS          7
        self.transfers = [
            # Incremental transfers
            TransferRatio("LB-01-02", 0, 1, config.LTB_THRESHOLD, 80),
            TransferRatio("LB-02-03", 1, 2, config.LTB_THRESHOLD, 80),
            TransferRatio("LB-03-BR", 2, 3, config.LTB_THRESHOLD, 50),
            TransferRatio("BR-BS-01", 3, 4, config.BTS_THRESHOLD, 80),
            TransferRatio("BS-01-02", 4, 5, config.BTS_THRESHOLD, 80),
            TransferRatio("BS-SR", 5, 6, config.BTS_THRESHOLD, 60),
            TransferRatio("BS-01-MS", 4, 7, config.BTS_THRESHOLD, 48),
            TransferRatio("BS-MS", 5, 7, config.BTS_THRESHOLD, 60),
            # Compound transfers from LB-01
            TransferRatio("LI-LB-03", 0, 2, config.LTB_THRESHOLD, 64),
            TransferRatio("LI-BR", 0, 3, config.LTB_THRESHOLD, 32),
            TransferRatio("LI-BS-01", 0, 4, config.LTB_THRESHOLD, 26),
            TransferRatio("LI-BS-02", 0, 5, config.LTB_THRESHOLD, 20),
            TransferRatio("LI-SR", 0, 6, config.LTB_THRESHOLD, 12),
            TransferRatio("LI-MS", 0, 7, config.LTB_THRESHOLD, 12),
            # Transfers from BR
            TransferRatio("BR-SR", 3, 6, config.BTS_THRESHOLD, 38),
            TransferRatio("BR-MS", 3, 7, config.BTS_THRESHOLD, 38),
        ]

        # Historical waveforms for booster and BTS-02 for 10 seconds, calculated
        # using offsets above
        self.histories = [
            #        0 BR            1 BS            2 SR            3 MS
            History(50, 3),
            History(50, 5),
            History(50, 6),
            History(50, 7),
        ]

        # Transfer efficiencies calculated as offsets into histories above
        self.transfers_2s = [
            TransferRatio("BR-SR2", 0, 2, config.BTS_THRESHOLD, 38),  # 3 -> 6
            TransferRatio("BS-SR2", 1, 2, config.BTS_THRESHOLD, 60),  # 5 -> 6
            TransferRatio("BR-MS2", 0, 3, config.BTS_THRESHOLD, 38),  # 3 -> 7
            TransferRatio("BS-MS2", 1, 3, config.BTS_THRESHOLD, 60),
        ]  # 5 -> 7
        self.transfers_10s = [
            TransferRatio("BR-SR10", 0, 2, config.BTS_THRESHOLD, 38),
            TransferRatio("BS-SR10", 1, 2, config.BTS_THRESHOLD, 60),
            TransferRatio("BR-MS10", 0, 3, config.BTS_THRESHOLD, 38),
            TransferRatio("BS-MS10", 1, 3, config.BTS_THRESHOLD, 60),
        ]

    def compute_ms_charge(self, values, valid, timestamps):
        """Computes MS:DELTAQ from mean MS reading, just a matter of scaling."""
        if valid[self.MS_CHARGE]:
            ms_charge = values[self.MS_CHARGE].mean * SR_MA_TO_NC
            self.dq_pv.set(ms_charge, timestamp=timestamps[self.MS_CHARGE])
            if numpy.isfinite(ms_charge):
                return (ms_charge, True)
            else:
                return (ms_charge, False)
        else:
            return (numpy.nan, False)

    def compute_sr_charge(self, values, valid, timestamps):
        """Computes SR delta Q from two successive DCCT updates."""
        signal_valid = valid[self.SR_SIGNAL]
        sr_charge = numpy.nan
        charge_valid = False
        if signal_valid:
            signal = values[self.SR_SIGNAL].value
            if self.last_signal_valid:
                sr_charge = (signal - self.last_signal) * SR_MA_TO_NC
                charge_valid = True
                self.charge_pv.set(sr_charge, timestamp=timestamps[self.SR_SIGNAL])
            self.last_signal = signal
        self.last_signal_valid = signal_valid

        return (sr_charge, charge_valid)

    def on_update(self, *args):
        # For each PV in the interval we are given the following data:
        #   values[i]   Value received during this interval for PV[i]
        #   valid[i]    Whether data was actually received
        #   origin      Timestamp of the baseline (injection timestamp)
        #   timestamps[i]   Timestamps of each PV
        #   arrivals[i] Arrival time of each PV
        values, valid, origin, timestamps, arrivals = args

        ms_charge, ms_charge_valid = self.compute_ms_charge(values, valid, timestamps)
        sr_charge, sr_charge_valid = self.compute_sr_charge(values, valid, timestamps)

        # Assemble a waveform of the values, using the computed charge for the
        # SR value and the mean MS value for the MS.
        values_wf = numpy.zeros(len(values))
        for i in range(self.SR_SIGNAL):
            values_wf[i] = values[i].value
        values_wf[self.SR_SIGNAL] = sr_charge
        valid[self.SR_SIGNAL] = sr_charge_valid
        values_wf[self.MS_CHARGE] = ms_charge
        valid[self.MS_CHARGE] = ms_charge_valid

        self.inject_pv.set(values_wf, timestamp=origin)

        # Compute the numerous transfer efficiencies
        for transfer in self.transfers:
            transfer.on_update(origin, values_wf, valid)

        # Accumulate histories for each desired incoming value
        for history in self.histories:
            history.add(values_wf, valid)

        # 2s = 10 samples
        histories = [history.mean(10) for history in self.histories]
        valid = list(map(numpy.isfinite, histories))
        for transfer in self.transfers_2s:
            transfer.on_update(origin, histories, valid)
        # 10s = 50 samples
        histories = [history.mean(50) for history in self.histories]
        valid = list(map(numpy.isfinite, histories))
        for transfer in self.transfers_10s:
            transfer.on_update(origin, histories, valid)


def setup(device_name="SR-DI-EBPM-01"):
    builder.SetDeviceName(device_name)
    Transfer()
