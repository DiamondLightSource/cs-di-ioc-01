# Classes for gathering multiple updates into a synchronous collection.
# Challenges include the underlying unreliability of the deliver mechanism
# (updates can be lost), the necessity to handling misaligned updates
# (timestamps are not always right), updates are not always timely (may be
# late), determination of update interval (can't just tick on an exact delay),
# and general robustness.


# Notes:
#   For each aggregate update we actually want quite a bit of information:
#       Whether this value is a good update
#       Actual value
#       Timestamp
#       ? Name
#
# How do we link updates to values?  Either by index in an array or by name.
# Clearly the Python way is by name.


import time
import numpy

import cothread
from cothread import catools
from softioc import builder
from autosuper import autosuper


INVALID_severity = 3


class IntervalController:
    '''Specifies a controller of synchronously updating values.'''

    def __init__(self, interval, delay, values, on_update,
            history_length = 2, adjust_iir = 0.5, finish_early = True):
        '''IntervalController(interval, values, ...)

        interval
            Specifies the expects interval in milliseconds between updates for
            this controller.  Needs to be reasonably accurate.

        delay
            Delay in milliseconds for accepting updates into the current
            interval.  Tune to ensure updates are not lost.

        values
            List of (value, shift) pairs, each value a ValueBase instance
            generating updates to be gathered, and shift a nominal timestamp
            shift (in milliseconds) to be applied to each update relative to the
            interval origin.

        on_update
            Called when an interval is complete.

        history_length
            Number of historical samples required to gather a single interval.

        adjust_iir = 0.5
            Controls how rapidly the interval start is tracked.

        finish_early = False
            Whether to generate update if all values have arrived before end of
            interval
        '''

        self.interval = 1e-3 * interval
        self.delay = 1e-3 * delay
        self.length = len(values)
        self.values, shifts = zip(*values)
        self.shifts = 1e-3 * numpy.array(shifts)
        self.on_update = on_update
        self.adjust_iir = adjust_iir
        self.finish_early = finish_early

        # Collection of values being managed by this controller
        for index, value in enumerate(self.values):
            value._register(self, index, history_length)
        self.value_ready = numpy.zeros(self.length, dtype = bool)

        # Start the timer.
        self.origin = time.time()
        self.timer = cothread.Timer(self.delay, self.__complete, reuse = True)

    def _get_interval(self, index, timestamp):
        '''Returns interval number.  The caller should have already applied any
        needed shift to the timestamp.'''
        return int(round(
            (timestamp - self.shifts[index] - self.origin) / self.interval))

    # Called by each value when it is complete
    def _ready(self, value):
        index = value.index
        if self.value_ready[index]:
            # Hmm.  We've already heard about this one.  Don't react again, and
            # log possible loss of information.
            print 'Duplicate ready notify from', value.name
        else:
            self.value_ready[index] = True
            if self.value_ready.all() and self.finish_early:
                # Might as well process the data now
                self.timer.reset(0)

    # Peforms completion, advances to the next interval
    def __complete(self):
        # Gather all final values: we're interested in value, validity and
        # timestamps.  At this point all individual update notifications will
        # occur.
        n = len(self.values)
        values = []
        valid = numpy.empty(n, dtype = bool)
        timestamps = numpy.empty(n)
        arrivals = numpy.empty(n)
        for i, value in enumerate(self.values):
            this = value._finalise()    # Generates individual update notify
            values.append(this)
            valid[i] = this.valid
            timestamps[i] = this.timestamp
            arrivals[i] = this.arrival

        # Compute the next interval
        old_origin = self.origin
        self.origin_offsets = timestamps - self.shifts - self.origin
        if valid.any():
            self.origin += self.adjust_iir * self.origin_offsets[valid].mean()
        self.origin += self.interval
        self.timer.reset(
            cothread.Deadline(self.origin + self.interval + self.delay))

        # Now do the aggregate update notification.
        self.on_update(values, valid, old_origin, timestamps, arrivals)

        # All done, prepare for next round of updates.
        self.value_ready[:] = False
        for value in self.values:
            value._advance()


class TriggerController:
    '''Used to gather data from a common trigger but without any predictable
    repetition interval.'''

    def __init__(self, delay, values, on_update):
        self.delay = 1e-3 * delay
        self.length = len(values)
        self.values, shifts = zip(*values)
        self.shifts = 1e-3 * numpy.array(shifts)
        self.on_update = on_update

        for index, value in enumerate(self.values):
            value._register(self, index, 1)
        self.value_ready = numpy.zeros(self.length, dtype = bool)

        self.timer = cothread.Timer(None, self.__complete, reuse = True)
        self.active = False

    def _get_interval(self, index, timestamp):
        if not self.active:
            self.active = True
            self.timer.reset(self.delay)
        return 0

    def _ready(self, value):
        index = value.index
        if self.value_ready[index]:
            print 'Duplicate ready notify from', value.name
        else:
            self.value_ready[index] = True
            if self.value_ready.all():
                self.timer.reset(0)

    def __complete(self):
        n = len(self.values)
        values = []
        valid = numpy.empty(n, dtype = bool)
        timestamps = numpy.empty(n)
        arrivals = numpy.empty(n)
        for i, value in enumerate(self.values):
            this = value._finalise()    # Generates individual update notify
            values.append(this)
            valid[i] = this.valid
            timestamps[i] = this.timestamp
            arrivals[i] = this.arrival

        # Compute the origin from timestamps and shifts
        origin = (timestamps - self.shifts)[valid].mean()

        self.on_update(values, valid, origin, timestamps, arrivals)

        self.value_ready[:] = False
        for value in self.values:
            value._advance()


class Controller_extra:
    '''A helper class for IntervalController which also publishes a number of
    interval diagnostic PVs.'''

    def __init__(self, name, controller):
        self.controller = controller
        self.valid_pv = builder.Waveform(
            '%s:VALID' % name, length = controller.length, datatype = bool,
            TSE = -2)
        self.ts_pv = builder.Waveform(
            '%s:TS' % name, length = controller.length, TSE = -2)
        self.age_pv = builder.Waveform(
            '%s:AGE' % name, length = controller.length, TSE = -2)
        self.offsets_pv = builder.Waveform(
            '%s:OFFSETS' % name, length = controller.length, TSE = -2)
        self.delay_pv = builder.aIn('%s:DELAY' % name, TSE = -2)

    def on_update(self, *args):
        now = time.time()
        values, valid, origin, timestamps, arrivals = args
        self.valid_pv.set(valid, timestamp = origin)
        self.ts_pv.set(1e3 * (timestamps - origin), timestamp = origin)
        self.age_pv.set(1e3 * (arrivals - origin), timestamp = origin)
        self.offsets_pv.set(
            1e3 * self.controller.origin_offsets, timestamp = origin)
        self.delay_pv.set(1e3 * (now - origin), timestamp = origin)



# ------------------------------------------------------------------------------
# ValueBase

class ValueBase(autosuper):
    def __init__(self, name, factory, on_update = None):
        self.name = name
        self.factory = factory
        self.__on_update = on_update

    # Called by the controller to complete initialisation of this value
    def _register(self, controller, index, history_length):
        self.values = [self.factory() for n in range(history_length)]
        self.controller = controller
        self.index = index

    # Called by the controller to finish up the value.  Returns the current
    # value.
    def _finalise(self):
        value = self.values[0]
        if self.validate(value):
            value.finalise()
            self.on_update(value)
        else:
            print 'not valid', self.name
        return value

    # Called by the controller to start a new interval.
    def _advance(self):
        value = self.values[0]
        value.advance(self.values[1])
        self.values = [value] + self.values[2:] + [self.factory()]
        if value.valid:
            self.controller._ready(self)

    def update(self, timestamp, value, *extra):
        '''To be called each time the underlying value has an update.  Arguments
        are the timestamp of the value, the value itself and any value dependent
        extra argument, such as the index for waveform element updates.'''
        interval = self.controller._get_interval(self.index, timestamp)
        if interval >= 0:
            try:
                value_base = self.values[interval]
            except IndexError:
                print 'Discarding early value', self.name, interval
            else:
                value_base.update(timestamp, value, *extra)
                if interval == 0 and value_base.valid:
                    self.controller._ready(self)
        else:
            # Value is too old, all we can do is discard it.
            print 'Discarding late value', self.name, interval

    def on_update(self, value):
        '''This method is called on completion of updates.'''
        if self.__on_update:
            self.__on_update(value)

    def validate(self, value):
        '''Called to validate the given value.'''
        return value.valid


# ------------------------------------------------------------------------------
# Single value update

class UpdateValue:
    def __init__(self):
        self.timestamp = numpy.nan
        self.valid = False
        self.value = numpy.nan
        self.arrival = numpy.nan
        self.timestamp = numpy.nan
        self.severity = INVALID_severity

    def update(self, timestamp, value):
        self.arrival = time.time()
        self.value = value
        self.timestamp = timestamp
        self.valid = True
        self.severity = value.severity

    def advance(self, next):
        if next.valid:
            self.value = next.value
            self.timestamp = next.timestamp
            self.arrival = next.arrival
            self.severity = next.severity
        self.valid = next.valid
# A question about advance -- do we discard missing data (essentialy
# reinitialise, in which case advance is actually pointless), or merge as here?
# Missing data is actually a bad sign...

    def finalise(self):
        pass


class Value(ValueBase):
    '''Specifies a single updating value.'''

    def __init__(self, name, **kargs):
        self.__super.__init__(name, UpdateValue, **kargs)


class Value_PV(Value):
    '''The usual case for a single data source: a single PV.'''

    def __init__(self, pv, **kargs):
        self.__super.__init__(pv, **kargs)
        catools.camonitor(pv, self.__pv_update, format = catools.FORMAT_TIME)

    def __pv_update(self, value):
        self.update(value.timestamp, value)


# ------------------------------------------------------------------------------
# Waveform value update

class UpdateWaveform:
    def __init__(self, length, validate = None):
        if validate is not None:
            self.validate = validate
        self.value        = numpy.zeros(length) + numpy.nan
        self.arrival_wf   = numpy.zeros(length) + numpy.nan
        self.timestamp_wf = numpy.zeros(length) + numpy.nan
        self.valid_wf     = numpy.zeros(length, dtype = bool)
        self.severity_wf  = \
            numpy.zeros(length, dtype = numpy.uint8) + INVALID_severity
        self.valid = False
        self.arrival = numpy.nan
        self.timestamp = numpy.nan

    def update(self, timestamp, value, index):
        self.arrival_wf[index] = time.time()
        self.value[index] = value
        self.timestamp_wf[index] = timestamp
        self.valid_wf[index] = True
        self.severity_wf[index] = value.severity
        self.valid = self.valid_wf.all()

    def advance(self, next):
        valid_wf = next.valid_wf
        self.value[valid_wf] = next.value[valid_wf]
        self.timestamp_wf[valid_wf] = next.timestamp_wf[valid_wf]
        self.arrival_wf[valid_wf] = next.arrival_wf[valid_wf]
        self.severity_wf[valid_wf] = next.severity_wf[valid_wf]
        self.valid_wf[:] = valid_wf
        self.valid = next.valid

    # Should only be called if this has been marked as a valid update
    def finalise(self):
        valid_wf = self.valid_wf
        self.timestamp = numpy.mean(self.timestamp_wf[valid_wf])
        self.arrival   = numpy.mean(self.arrival_wf[valid_wf])
        self.severity  = numpy.max(self.severity_wf[valid_wf])


class Waveform(ValueBase):
    '''Specifies a waveform of updating values.'''

    def __init__(self, name, length, validate = None, **kargs):
        self.__super.__init__(name, lambda: UpdateWaveform(length), **kargs)

        if validate is not None:
            self.validate = validate

    def validate(self, value):
        '''This can be overwritten or specified in the constructor.  By default
        the waveform is accepted if any one value received an update.'''
        value.valid = value.valid_wf.any()
        return value.valid


class Waveform_PV(Waveform):
    '''A waveform aggregated from a collection of independently updating PVs.
    Only really works properly if there is some kind of synchronisation among
    the contributing PVs.'''

    def __init__(self, name, pvs, **kargs):
        self.__super.__init__(name, len(pvs), **kargs)
        catools.camonitor(pvs, self.__pv_update, format = catools.FORMAT_TIME)

    def __pv_update(self, value, index):
        self.update(value.timestamp, value, index)


# ------------------------------------------------------------------------------
# Waveform publishing helper classes

class Waveform_Out:
    '''Simple waveform.'''

    def __init__(self, name, length, datatype = None):
        self.pv = builder.Waveform(
            name, length = length, datatype = datatype, TSE = -2)

    def on_update(self, value):
        self.pv.set(value.value, timestamp = value.timestamp)


class MaskedWaveform(Waveform_PV):
    def __init__(self, name, mask, default = 0, shift = 0):
        # The mask is a mutable value which is managed externally
        self.mask = mask
        self.default = default

        pvs = ['%s:%s' % (bpm, name) for bpm in bpm_list.BPMS]
        self.__super.__init__(name, pvs, shift = shift)

        length = len(pvs)
        self.wf_raw = builder.Waveform(
            '%s:RAW' % name, length = length, TSE = -2)
        self.wf_out = builder.Waveform(name, length = length, TSE = -2)
        self.wf_ts = intervals.Waveform_TS(
            '%s:TS' % name, '%s:AGE' % name, length)

    def set_default(self, default):
        self.default = default

    def on_update(self, value):
        ts = value.timestamp
        wf = value.value
        self.masked_value = numpy.where(self.mask, wf, self.default)
        self.wf_raw.set(wf, timestamp = ts)
        self.wf_out.set(self.masked_value, timestamp = ts)

        self.wf_ts.on_update(value)
        self.__super.on_update(value)



class Waveform_TS:
    '''Relative timestamp and age waveforms.'''

    def __init__(self, ts_name, age_name, length):
        self.ts_pv  = builder.Waveform(
            ts_name,  length = length, EGU = 'ms', TSE = -2)
        self.age_pv = builder.Waveform(
            age_name, length = length, EGU = 'ms', TSE = -2)

    def on_update(self, value):
        ts = value.timestamp
        self.ts_pv .set(1e3 * (value.timestamp_wf - ts), timestamp = ts)
        self.age_pv.set(1e3 * (value.arrival_wf - ts),   timestamp = ts)


class Waveform_Mean:
    '''Average value waveform.'''

    def __init__(self, name, **kargs):
        self.mean_pv = builder.aIn(name, TSE = -2, **kargs)

    def on_update(self, value):
        value.mean = numpy.mean(value.value[value.valid_wf])
        self.mean_pv.set(value.mean, timestamp = value.timestamp)
