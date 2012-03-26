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


class Controller(object):
    '''Specifies a controller of synchronously updating values.'''

    def __init__(self, interval, values,
            delay = 0, adjust_iir = 0.5, acceptance = 0.5,
            finish_early = False, on_update = None):
        '''Controller(interval, values, ...)

        interval
            Specifies the expects interval in milliseconds between updates for
            this controller.  Needs to be reasonably accurate.
        values
            List of ValueBase instances to generate updates to be gathered.

        delay = 0
            Delay in milliseconds for accepting updates into the current
            interval.  Tune to ensure updates are not lost.

        adjust_iir = 0.5
            Controls how rapidly the interval start is tracked.

        acceptance = 0.5
            Acceptance interval for updates in fractions of an interval.

        finish_early = False
            Whether to generate update if all values have arrived before end of
            acceptance interval

        on_update
            Called when an interval is complete.
        '''

        assert acceptance <= 1, 'Overlapping acceptance interval won\'t work'

        self.interval = 1e-3 * interval
        self.values = values
        self.delay = 1e-3 * delay
        self.adjust_iir = adjust_iir
        self.acceptance = 0.5 * self.interval
        self.finish_early = finish_early
        self.__on_update = on_update

        # Interval management settings
        self.origin = time.time()

        # Collection of values being managed by this controller
        self.shifts = numpy.zeros(len(self.values))
        for index, value in enumerate(self.values):
            self.shifts[index] = value._register(self, index)
        self.value_ready = numpy.zeros(len(self.values), dtype = bool)

        # Start by expiring as soon as possible.  Until we've done our first
        # completion none of the updaters have an interval to work with.
        self.timer = cothread.Timer(0, self.__complete, reuse = True)


    # Called by each value when it is complete
    def _ready(self, value):
        index = value.index
        if self.value_ready[index]:
            # Hmm.  We've already heard about this one.  Don't react again, and
            # log possible loss of information
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
        valid = numpy.empty(n, dtype = bool)
        values = []
        timestamps = numpy.empty(n)
        arrivals = numpy.empty(n)
        for i, value in enumerate(self.values):
            this = value._finalise()    # Generates individual update notify
            valid[i] = this.valid
            values.append(this.value)
            timestamps[i] = this.timestamp
            arrivals[i] = this.arrival

        # Now do the aggregate update notification.
        self.on_update(self.origin, valid, values, timestamps, arrivals)

        # Compute the next interval
        if valid.any():
            self.origin += self.adjust_iir * \
                (timestamps[valid] - self.shifts[valid] - self.origin).mean()
        self.origin += self.interval
        self.timer.reset(cothread.Deadline(
            self.origin + self.interval + self.delay))

        # All done, prepare for next round of updates and give each value its
        # new acceptance interval.
        self.value_ready[:] = False
        interval = (
            self.origin - self.acceptance, self.origin + self.acceptance)
        for value in self.values:
            value._advance(interval)


    def on_update(self, *args):
        '''Default update method does nothing.  Can be overridden in constructor
        or by subclassing.'''
        if self.__on_update:
            self.__on_update(*args)


class ValueBase(object):
    def __init__(self, name, shift = 0, on_update = None):
        self.name = name
        self.shift = 1e-3 * shift
        self.interval = (0, 0)
        self.__on_update = on_update

    # Called by the controller to complete initialisation of this value
    def _register(self, controller, index):
        self.controller = controller
        self.index = index
        return self.shift

    # Called by the controller to finish up the value.  Returns the current
    # value.
    def _finalise(self):
        if self.validate(self.this):
            self.this.finalise()
            self.on_update(self.this)
        else:
            print 'not valid', self.name
        return self.this

    # Called by the controller to start a new interval.
    def _advance(self, interval):
        self.this.advance(self.next)
        if self.this.valid:
            self.controller._ready(self)
        self.interval = interval


    def update(self, timestamp, value, *extra):
        '''To be called each time the underlying value has an update.  Arguments
        are the timestamp of the value, the value itself and any value dependent
        extra argument, such as the index for waveform element updates.'''
        start, end = self.interval
        ts = timestamp - self.shift

        if ts < start:
            # Value is too old, all we can do is discard it.
            print 'Discarding', self.name, \
                '%.2f ms late' % (1e3 * (start - ts))
        elif ts < end:
            # Current value, process as current and notify completion if
            # appropriate.
            self.this.update(timestamp, value, *extra)
            if self.this.valid:
                self.controller._ready(self)
        else:
            # Early value, remember this in preparation for next interval.
            self.next.update(timestamp, value, *extra)

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

    def update(self, timestamp, value):
        self.arrival = time.time()
        self.value = value
        self.timestamp = timestamp
        self.valid = True

    def advance(self, next):
        if next.valid:
            self.value = next.value
            self.timestamp = next.timestamp
            self.arrival = next.arrival
        self.valid = next.valid
        next.valid = False

    def finalise(self):
        pass


class Value(ValueBase):
    '''Specifies a single updating value.'''

    def __init__(self, name, **kargs):
        super(Value, self).__init__(name, **kargs)
        self.this = UpdateValue()
        self.next = UpdateValue()


class Value_PV(Value):
    '''The usual case for a single data source: a single PV.'''

    def __init__(self, pv, **kargs):
        super(Value_PV, self).__init__(pv, **kargs)
        catools.camonitor(pv, self.__pv_update, format = catools.FORMAT_TIME)

    def __pv_update(self, value):
        self.update(value.timestamp, value)


# ------------------------------------------------------------------------------
# Waveform value update

class UpdateWaveform:
    def __init__(self, length, validate = None):
        if validate is not None:
            self.validate = validate
        self.value = numpy.zeros(length)
        self.arrival_wf = numpy.zeros(length)
        self.timestamp_wf = numpy.zeros(length)
        self.valid_wf = numpy.zeros(length, dtype = bool)
        self.valid = False
        self.arrival = numpy.nan
        self.timestamp = numpy.nan

    def update(self, timestamp, value, index):
        self.arrival_wf[index] = time.time()
        self.value[index] = value
        self.timestamp_wf[index] = timestamp
        self.valid_wf[index] = True
        self.valid = self.valid_wf.all()

    def advance(self, next):
        valid_wf = next.valid_wf
        self.value[valid_wf] = next.value[valid_wf]
        self.timestamp_wf[valid_wf] = next.timestamp_wf[valid_wf]
        self.arrival_wf[valid_wf] = next.arrival_wf[valid_wf]
        self.valid_wf[:] = valid_wf
        next.valid_wf[:] = False
        self.valid = next.valid
        next.valid = False

    # Should only be called if this has been marked as a valid update
    def finalise(self):
        valid_wf = self.valid_wf
        self.timestamp = numpy.mean(self.timestamp_wf[valid_wf])
        self.arrival   = numpy.mean(self.arrival_wf[valid_wf])


class Waveform(ValueBase):
    '''Specifies a waveform of updating values.'''

    def __init__(self, name, length, validate = None, **kargs):
        super(Waveform, self).__init__(name, **kargs)
        self.this = UpdateWaveform(length)
        self.next = UpdateWaveform(length)
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
        super(Waveform_PV, self).__init__(name, len(pvs), **kargs)
        catools.camonitor(pvs, self.__pv_update, format = catools.FORMAT_TIME)

    def __pv_update(self, value, index):
        self.update(value.timestamp, value, index)


class Waveform_PV_Out(Waveform_PV):
    def __init__(self, name, pvs, datatype = None, **kargs):
        super(Waveform_PV_Out, self).__init__(name, pvs, **kargs)
        self.pv = builder.Waveform(
            name, numpy.zeros(len(pvs)), datatype = datatype, TSE = -2)

    def on_update(self, value):
        if not value.valid_wf.all():
            print 'bad update', value.valid_wf
        self.pv.set(value.value, timestamp = value.timestamp)
        if self.mean_pv is not None:
            self.mean_pv.set(
                numpy.mean(value.value[value.valid_wf]),
                timestamp = value.timestamp)


# Adds MEAN, AGE and TS PVs.
class Waveform_PV_extra(Waveform_PV_Out):
    def __init__(self, name, pvs, datatype = float, **kargs):
        super(Waveform_PV_extra, self).__init__(name, pvs, **kargs)

        z = numpy.zeros(len(pvs))
        self.mean_pv = builder.aIn('%s:MEAN' % name, TSE = -2)
        self.ts_pv = builder.Waveform(
            '%s:TS' % name, +z, EGU = 'ms', TSE = -2)
        self.age_pv = builder.Waveform(
            '%s:AGE' % name, +z, EGU = 'ms', TSE = -2)

    def on_update(self, value):
        super(Waveform_PV_extra, self).on_update(value)
        ts = value.timestamp
        self.mean_pv.set(
            numpy.mean(value.value[value.valid_wf]), timestamp = ts)
        self.ts_pv.set(1e3 * (value.timestamp_wf - ts), timestamp = ts)
        self.age_pv.set(1e3 * (value.arrival_wf - ts), timestamp = ts)


class Controller_extra(Controller):
    '''An implementation of Controller which also publishes a number of interval
    diagnostic PVs.'''

    def __init__(self, name, interval, values, **kargs):
        super(Controller_extra, self).__init__(interval, values, **kargs)

        z = numpy.zeros(len(values))
        self.valid_pv = builder.Waveform(
            '%s:VALID' % name, +z, datatype = bool, TSE = -2)
        self.ts_pv = builder.Waveform('%s:TS' % name, +z, TSE = -2)
        self.age_pv = builder.Waveform('%s:AGE' % name, +z, TSE = -2)

    def on_update(self, origin, valid, values, timestamps, arrivals):
        super(Controller_extra, self).on_update(origin, values)
        self.valid_pv.set(valid, timestamp = origin)
        self.ts_pv.set(1e3 * (timestamps - origin), timestamp = origin)
        self.age_pv.set(1e3 * (arrivals - origin), timestamp = origin)
