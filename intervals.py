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


VERBOSE = False


INVALID_severity = 3


class ControllerBase(autosuper):
    '''Captures common features of all controllers.'''

    def __init__(self,
            delay, initial_delay, values, on_update, history_length,
            finish_early = True):
        self.delay = 1e-3 * delay
        self.length = len(values)
        self.values, shifts = zip(*values)
        self.shifts = 1e-3 * numpy.array(shifts)
        self.on_update = []
        if on_update is not None:
            self.hook_onupdate(on_update)
        self.finish_early = finish_early

        for index, value in enumerate(self.values):
            value._register(self, index, history_length)
        self.value_ready = numpy.zeros(self.length, dtype = bool)

        self.timer = cothread.Timer(
            initial_delay, self.__complete, reuse = True)

    def hook_onupdate(self, on_update):
        self.on_update.append(on_update)

    # Called by each value when it is complete
    def _ready(self, index):
        if not self.value_ready[index]:
            self.value_ready[index] = True
            if self.finish_early and self.value_ready.all():
                # Might as well process the data now
                self.timer.reset(0)

    def __complete(self):
        # Gather the values and timestamps for this update.
        values = []
        valid = numpy.empty(self.length, dtype = bool)
        timestamps = numpy.empty(self.length)
        arrivals = numpy.empty(self.length)
        for i, value in enumerate(self.values):
            this = value._finalise()    # Generates individual update notify
            values.append(this)
            valid[i] = this.valid
            timestamps[i] = this.timestamp
            arrivals[i] = this.arrival

        # Compute the origin from timestamps and shifts.  May also start timer
        # for the next interval.
        origin = self._compute_origin(timestamps, valid)

        for update in self.on_update:
            update(values, valid, origin, timestamps, arrivals)

        self.value_ready[:] = False
        for value in self.values:
            value._advance()


class IntervalController(ControllerBase):
    '''Specifies a controller of synchronously updating values.'''

    def __init__(self, interval, delay, values, on_update = None,
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

        self.__super.__init__(
            delay, 1e-3 * delay, values, on_update, history_length,
            finish_early)

        self.interval = 1e-3 * interval
        self.adjust_iir = adjust_iir
        self.origin = time.time()

    def _get_interval(self, index, timestamp):
        '''Returns interval number.  The caller should have already applied any
        needed shift to the timestamp.'''
        return int(round(
            (timestamp - self.shifts[index] - self.origin) / self.interval))

    def _compute_origin(self, timestamps, valid):
        origin = self.origin
        self.origin_offsets = timestamps - self.shifts - self.origin
        if valid.any():
            offset = self.adjust_iir * self.origin_offsets[valid].mean()
            self.origin += offset
        self.origin += self.interval
        self.timer.reset(
            cothread.Deadline(self.origin + self.interval + self.delay))
        return origin


class TriggeredController(ControllerBase):
    '''Used to gather data from a common trigger but without any predictable
    repetition interval.'''

    def __init__(self, delay, values, on_update = None, finish_early = True):
        '''
        delay
            Milliseconds after first trigger when aggregate update will be
            generated.
        values
            List of values managed by this controller.
        on_update
            Called when update is complete.
        finish_early
            If set will complete as soon as all values are ready.
        '''
        self.__super.__init__(delay, None, values, on_update, 1, finish_early)
        self.active = False

    def _get_interval(self, index, timestamp):
        if not self.active:
            self.active = True
            self.timer.reset(self.delay)
        return 0

    def _compute_origin(self, timestamps, valid):
        return (timestamps - self.shifts)[valid].mean()


class IrregularController:
    '''Gathers irregularly updating data with minimum refractory interval and
    minimum delay before update.'''

    # The update and holdoff delays are used to prevent a cascade of updates
    # when lots of updates are being received.  First the update_delay is used
    # to pause after a first event is seen so that any further updates can be
    # processed.  Secondly, the holdoff_delay is used to prevent immediate
    # retriggering.

    def __init__(self, update_delay, holdoff_delay, values):
        self.update_delay  = 1e-3 * update_delay
        self.holdoff_delay = 1e-3 * holdoff_delay
        self.values = values

        for index, value in enumerate(self.values):
            value._register(self, index, 1)
        self.waiting = False
        self.holdoff = False

    def _ready(self, index):
        pass

    def _get_interval(self, index, timestamp):
        if not self.waiting:
            self.waiting = True
            if not self.holdoff:
                cothread.Timer(self.update_delay, self.__complete)
        return 0

    def __complete(self):
        self.waiting = False
        self.holdoff = True
        cothread.Timer(self.holdoff_delay, self.__holdoff)

        for value in self.values:
            # Note that we don't advance the values.
            value._finalise()

    def __holdoff(self):
        self.holdoff = False
        if self.waiting:
            self.__complete()



class Controller_extra:
    '''A helper class for IntervalController which also publishes a number of
    interval diagnostic PVs.'''

    def __init__(self, name, controller):
        self.controller = controller
        controller.hook_onupdate(self.on_update)
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
        self.controller = controller
        self.index = index
        self.values = [self.factory() for n in range(history_length)]

    # Called by the controller to finish up the value.  Returns the current
    # value.
    def _finalise(self):
        value = self.values[0]
        if self.validate(value):
            value.finalise()
            self.on_update(value)
        else:
            if VERBOSE:
                print 'not valid', self.name
        return value

    # Called by the controller to start a new interval.
    def _advance(self):
        self.values = self.values[1:] + [self.factory()]
        if self.values[0].valid:
            self.controller._ready(self.index)

    def update(self, timestamp, value, *extra):
        '''To be called each time the underlying value has an update.  Arguments
        are the timestamp of the value, the value itself and any value dependent
        extra argument, such as the index for waveform element updates.'''
#         if numpy.random.randint(10) == 0: return    # Discard random data
#         timestamp += 0.04 * numpy.random.randn()    # Fuzz the timestamp

        interval = self.controller._get_interval(self.index, timestamp)
        if interval >= 0:
            try:
                value_base = self.values[interval]
            except IndexError:
                if VERBOSE:
                    print 'Discarding early value', self.name, interval
            else:
                value_base.update(timestamp, value, *extra)
                if interval == 0 and value_base.valid:
                    self.controller._ready(self.index)
        else:
            # Value is too old, all we can do is discard it.
            if VERBOSE:
                print 'Discarding late value', self.name, interval

    def on_update(self, value):
        '''This method is called on completion of updates.'''
        if self.__on_update:
            self.__on_update(value)

    def validate(self, value):
        '''Called to validate the given value.'''
        return value.valid


# ------------------------------------------------------------------------------
# Core Value classes.

class UpdateValue:
    def __init__(self):
        self.value = numpy.nan
        self.arrival = numpy.nan
        self.timestamp = numpy.nan
        self.valid = False
        self.severity = INVALID_severity

    def update(self, timestamp, value):
        self.value = value
        self.arrival = time.time()
        self.timestamp = timestamp
        self.valid = True
        self.severity = value.severity

    def finalise(self):
        pass


class UpdateWaveform:
    def __init__(self, length):
        self.value        = numpy.zeros(length) + numpy.nan
        self.arrival_wf   = numpy.zeros(length) + numpy.nan
        self.timestamp_wf = numpy.zeros(length) + numpy.nan
        self.valid_wf     = numpy.zeros(length, dtype = bool)
        self.severity_wf  = \
            numpy.zeros(length, dtype = numpy.uint8) + INVALID_severity

        self.valid = False
        self.arrival = numpy.nan
        self.timestamp = numpy.nan
        self.severity = INVALID_severity

    def update(self, timestamp, value, index):
        self.value[index] = value
        self.arrival_wf[index] = time.time()
        self.timestamp_wf[index] = timestamp
        self.valid_wf[index] = True
        self.severity_wf[index] = value.severity

        self.valid = self.valid_wf.all()

    # Should only be called if this has been marked as a valid update
    def finalise(self):
        valid_wf = self.valid_wf
        self.timestamp = numpy.mean(self.timestamp_wf[valid_wf])
        self.arrival   = numpy.mean(self.arrival_wf[valid_wf])
        self.severity  = numpy.max(self.severity_wf[valid_wf])


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


class Waveform_TS:
    '''Helper class for published waveforms with timestamps.'''

    def __init__(self, length, raw_name, ts_name = None, age_name = None):
        if ts_name is None:
            ts_name = '%s:TS' % raw_name
        if age_name is None:
            age_name = '%s:AGE' % raw_name
        self.wf_raw = builder.Waveform(raw_name, length = length, TSE = -2)
        self.wf_age = builder.Waveform(age_name, length = length, TSE = -2)
        self.wf_ts  = builder.Waveform(ts_name,  length = length, TSE = -2)

    def on_update(self, value):
        ts = value.timestamp
        self.wf_raw.set(value.value, timestamp = ts)
        self.wf_age.set(1e3 * (value.arrival_wf - ts), timestamp = ts)
        self.wf_ts.set(1e3 * (value.timestamp_wf - ts), timestamp = ts)


class Waveform_Out(Waveform_PV):
    '''Simple waveform with associated timestamps.'''

    def __init__(self, name, pvs, **kargs):
        self.__super.__init__(name, pvs, **kargs)
        self.wf = Waveform_TS(len(pvs), name)

    def on_update(self, value):
        self.__super.on_update(value)
        self.wf.on_update(value)


class MaskedWaveform(Waveform_PV):
    def __init__(self, name, pvs, mask = None, offset = 0, **kargs):
        self.__super.__init__(name, pvs, **kargs)

        # The mask is a mutable pair consisting of a boolean mask of values (in
        # the first element) to be replaced with the default (in the second
        # element).
        self.mask = mask
        self.offset = offset

        length = len(pvs)
        self.wf_out = builder.Waveform(name, length = length, TSE = -2)
        self.wf_ts = Waveform_TS(
            length, '%s:RAW' % name, '%s:TS' % name, '%s:AGE' % name)

    def on_update(self, value):
        self.__super.on_update(value)
        self.wf_ts.on_update(value)

        if self.mask:
            mask, default = self.mask
            self.masked_value = numpy.where(mask, value.value, default)
        else:
            self.masked_value = +value.value
        if self.offset:
            self.masked_value -= self.offset
        self.wf_out.set(self.masked_value, timestamp = value.timestamp)


class Waveform_Mean:
    '''Average value waveform.'''

    def __init__(self, name, **kargs):
        self.mean_pv = builder.aIn(name, TSE = -2, **kargs)

    def on_update(self, value):
        value.mean = numpy.mean(value.value[value.valid_wf])
        self.mean_pv.set(value.mean, timestamp = value.timestamp)
