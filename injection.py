# PVs for injection calculation.

import numpy
import cothread
from softioc import builder

import intervals


F_RF = 499654097        # 60 cm
SR_BUNCHES = 936        # 561.6 m
SR_MA_TO_NC = 1e6 * SR_BUNCHES / F_RF       # 1.87 us (534 kHz)


class MS_Waveform(intervals.Waveform_PV):
    ms_pvs = ['SR%02dC-DI-EBPM-%02d:MS:DELTAI' % (c+1, n+1)
        for c in range(24) for n in range(7)]

    def __init__(self, shift):
        self.__super.__init__('MS:DELTAI', self.ms_pvs, shift = shift)

        N = len(self.ms_pvs)
        self.wf_out = intervals.Waveform_Out('MS:DELTAI', N)
        self.wf_ts = intervals.Waveform_TS('MS:DELTAI:TS', 'MS:DELTAI:AGE', N)
        self.mean_pv = intervals.Waveform_Mean('MS:DELTAI:MEAN')

    def on_update(self, value):
        self.wf_out.on_update(value)
        self.wf_ts.on_update(value)
        self.mean_pv.on_update(value)

        self.__super.on_update(value)


class TransferRatio:
    '''Manages transfer ratio for a single pair of values.'''

    def __init__(self, name, input, output):
        self.name = name
        self.input = input
        self.output = output
        self.pv = builder.aIn(
            name, 0, 100, PREC = 2, EGU = '%', MDEL = -1, TSE = -2)

    def on_update(self, timestamp, values, valid):
        if valid[self.input] and valid[self.output]:
            input  = values[self.input]
            output = values[self.output]
            if input > 0.05:
                xfer = 100. * output / input
            else:
                xfer = 0
            self.pv.set(xfer, timestamp = timestamp)


class History:
    '''Historical waveforms with remembered validity.  As for TransferRatio, we
    pick up the values from waveforms passed in'''

    def __init__(self, length, index):
        self.index = index
        self.history = numpy.zeros(length)
        self.valid = numpy.zeros(length, dtype = bool)

    def add(self, values, valid):
        self.history = numpy.roll(self.history, -1)
        self.valid = numpy.roll(self.valid, -1)
        self.history[-1] = values[self.index]
        self.valid[-1] = valid[self.index]

    def mean(self, length):
        return self.history[-length:][self.valid[-length:]].mean()


class Transfer:
    '''Transfer efficiency calculation'''

    xfr_pvs = [
        ('LB-DI-ICT-01:SIGNAL',     0),     # 0
        ('LB-DI-ICT-02:SIGNAL',     0),     # 1
        ('LB-DI-ICT-03:SIGNAL',     200),   # 2
        ('BR01C-DI-DCCT-01:CHARGE', 200),   # 3
        ('BS-DI-ICT-01:SIGNAL',     99),    # 4
        ('BS-DI-ICT-02:SIGNAL',     99),    # 5
        ('SR21C-DI-DCCT-01:SIGNAL', 200),   # 6
    ]

    SR_SIGNAL = 6
    MS_CHARGE = 7

    acceptance = 0.5

    def __init__(self):
        builder.SetDeviceName('TS-DI-TEST-01')
        pvs = [
            intervals.Value_PV(pv, shift = shift)
                for pv, shift in self.xfr_pvs] + [
            MS_Waveform(303.8)
            ]
        self.controller = intervals.Controller(
            200, pvs,
            history_length = 3, delay = 350, finish_early = True,
            acceptance = 0.5, on_update = self.on_update)

        self.extra = intervals.Controller_extra('INJECT', self.controller)
        self.dq_pv = builder.aIn('MS:DELTAQ', 0, 1,
            PREC = 3, EGU = 'nC', TSE = -2)
        self.inject_pv = builder.Waveform(
            'INJECT:VALUES', numpy.zeros(len(pvs)), TSE = -2)

        # Transfer efficiency PVs.  These are all CS-DI-XFER-01 PVs
        builder.SetDeviceName('CS-DI-XFER-01')

        self.charge_pv = builder.aIn('SR:CHARGE', 0, 1,
            PREC = 3, EGU = 'nC', TSE = -2)
        self.last_signal_valid = False

        # Historical waveforms for booster and BTS-02 for 10 seconds
        self.histories = [
            #          BR              BS              SR              MS
            History(50, 3), History(50, 5), History(50, 6), History(50, 7)]

        # Transfer efficiencies calculated as offsets into interval
        self.transfers = [
            TransferRatio('LB-01-02', 0, 1),
            TransferRatio('LB-02-03', 1, 2),  TransferRatio('LI-LB-03', 0, 2),
            TransferRatio('LB-03-BR', 2, 3),  TransferRatio('LI-BR',    0, 3),
            TransferRatio('BR-BS-01', 3, 4),  TransferRatio('LI-BS-01', 0, 4),
            TransferRatio('BS-01-02', 4, 5),  TransferRatio('LI-BS-02', 0, 5),
            TransferRatio('BS-SR',    5, 6),  TransferRatio('LI-SR',    0, 6),
            TransferRatio('BR-SR',    3, 6),
            TransferRatio('BS-MS',    5, 7),  TransferRatio('LI-MS',    0, 7),
            TransferRatio('BR-MS',    3, 7)]

        # Transfer efficiencies calculated as offsets into histories
        self.transfers_2s = [
            TransferRatio('BR-SR2', 0, 2),     TransferRatio('BS-SR2', 1, 2),
            TransferRatio('BR-MS2', 0, 3),     TransferRatio('BS-MS2', 1, 3)]
        self.transfers_10s = [
            TransferRatio('BR-SR10', 0, 2),    TransferRatio('BS-SR10', 1, 2),
            TransferRatio('BR-MS10', 0, 3),    TransferRatio('BS-MS10', 1, 3)]


    def compute_ms_charge(self, values, valid, timestamps):
        if valid[self.MS_CHARGE]:
            ms_charge = values[self.MS_CHARGE].mean * SR_MA_TO_NC
            self.dq_pv.set(ms_charge, timestamp = timestamps[self.MS_CHARGE])
            return (ms_charge, True)
        else:
            return (numpy.nan, False)

    def compute_sr_charge(self, values, valid, timestamps):
        '''Computes SR delta Q from two successive DCCT updates.'''
        signal_valid = valid[self.SR_SIGNAL]
        sr_charge = numpy.nan
        charge_valid = False
        if signal_valid:
            signal = values[self.SR_SIGNAL].value
            if self.last_signal_valid:
                sr_charge = (signal - self.last_signal) * SR_MA_TO_NC
                charge_valid = True
                self.charge_pv.set(
                    sr_charge, timestamp = timestamps[self.SR_SIGNAL])
            self.last_signal = signal
        self.last_signal_valid = signal_valid

        return (sr_charge, charge_valid)


    def on_update(self, *args):
        self.extra.on_update(*args)

        values, valid, origin, timestamps, arrivals = args

        ms_charge, ms_charge_valid = \
            self.compute_ms_charge(values, valid, timestamps)
        sr_charge, sr_charge_valid = \
            self.compute_sr_charge(values, valid, timestamps)

        # Assemble a waveform of the values, using the computed charge for the
        # SR value and the mean MS value for the MS.
        values_wf = numpy.zeros(len(values))
        for i in range(self.SR_SIGNAL):
            values_wf[i] = values[i].value
        values_wf[self.SR_SIGNAL] = sr_charge
        valid[self.SR_SIGNAL] = sr_charge_valid
        values_wf[self.MS_CHARGE] = ms_charge

        self.inject_pv.set(values_wf, timestamp = origin)

        for transfer in self.transfers:
            transfer.on_update(origin, values_wf, valid)

        for history in self.histories:
            history.add(values_wf, valid)

        # 2s = 10 samples
        histories = [history.mean(10) for history in self.histories]
        valid = map(numpy.isfinite, histories)
        for transfer in self.transfers_2s:
            transfer.on_update(origin, histories, valid)
        # 10s = 50 samples
        histories = [history.mean(50) for history in self.histories]
        valid = map(numpy.isfinite, histories)
        for transfer in self.transfers_10s:
            transfer.on_update(origin, histories, valid)


Transfer()
