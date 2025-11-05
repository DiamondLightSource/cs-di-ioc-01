# Beam Correction Deviation
#
# BCD used to stand for Beam Current Deviation and was a correction to be
# applied to correct for changes in BPM response as beam current changed.
# However after correction of cable lengths and with topup operation this
# correction is no longer useful.
#
# BCD now stands for an instantaneous and small adjustment to beam position to
# make small adjustments in beam position required for instant to instant
# beamline operation.

import cothread
from cothread import catools
from softioc import alarm, builder

import concentrator.bpm_list as bpm_list
from concentrator.config import *


# Manages interface to a single BCD value.  Wraps a camonitor with a local copy
# of the updated value and wraps writing to the value with an implementation of
# slewing.
#   This class also translates between microns and millimetres: the interface to
# external PV is in millimetres, but internally we work in microns.
class BCD_PV:
    def __init__(self, name, on_update):
        self.name = name
        self.on_update = on_update

        self.value = 0
        catools.camonitor(name, self.__update)

        self.target = None
        self.ready = cothread.Event()
        cothread.Spawn(self.__slewing)

    def __update(self, value):
        self.value = 1e3 * value  # Convert PV from mm to microns
        self.on_update()

    def put(self, value):
        self.target = value
        self.ready.Signal()

    # Computes target for a single update
    def __compute_target(self):
        delta = self.target - self.value
        max_step = slew_rate.get() * BCD_SLEW_INTERVAL
        if abs(delta) <= max_step:
            return self.target
        elif delta > 0:
            return self.value + max_step
        else:
            return self.value - max_step

    def __slewing(self):
        while True:
            self.ready.Wait()

            while self.target is not None:
                target = self.__compute_target()
                if target == self.target:
                    self.target = None

                e = catools.caput(self.name, 1e-3 * target, throw=False)
                if not e:
                    print("update failed:", e)
                    self.target = None
                    self.on_update()

                cothread.Sleep(BCD_SLEW_INTERVAL)


# Clip values a, b to most extreme possible value against each limit.
def constrain_bcd(a, b):
    def clip(l, a, b):
        return (l, l / a * b)

    limit = bcd_limit.get()
    if a > limit:
        a, b = clip(limit, a, b)
    elif a < -limit:
        a, b = clip(-limit, a, b)
    if b > limit:
        b, a = clip(limit, b, a)
    elif b < -limit:
        b, a = clip(-limit, b, a)
    return (a, b)


# BCD control for a single axis: controls end points (called left and right) in
# response to settings of offset and angle.
class Axis:
    # All axes are accumulated into a list so we can perform operations on all
    # axes, in particular refreshing limits when the bcd_limit changes.
    all_axes = []

    def __init__(self, parent, axis, length, centre, left, right):
        def pv_name(field):
            return "%s:%s" % (axis, field)

        self.all_axes.append(self)

        self.parent = parent

        self.length = length
        self.centre = centre

        self.target_offset = builder.aOut(
            pv_name("OFFSET_S"),
            EGU="um",
            PREC=2,
            initial_value=0,
            always_update=True,
            validate=self.check_enabled,
            on_update=self.set_target,
        )
        self.target_angle = builder.aOut(
            pv_name("ANGLE_S"),
            EGU="u rad",
            PREC=2,
            initial_value=0,
            always_update=True,
            validate=self.check_enabled,
            on_update=self.set_target,
        )

        self.min_offset = builder.aIn(pv_name("OFFSET:MIN"), PREC=2, EGU="um")
        self.max_offset = builder.aIn(pv_name("OFFSET:MAX"), PREC=2, EGU="um")
        self.min_angle = builder.aIn(pv_name("ANGLE:MIN"), PREC=2, EGU="u rad")
        self.max_angle = builder.aIn(pv_name("ANGLE:MAX"), PREC=2, EGU="u rad")

        # Monitor and control for the two BCD settings we need to manage.
        self.left = BCD_PV("%s:CF:BCD_%s_S" % (left, axis), self.update_bcd)
        self.right = BCD_PV("%s:CF:BCD_%s_S" % (right, axis), self.update_bcd)
        # Mirror the left and right BCD settings so that we have uniform PV
        # names for use on the common display.  These mirrors are in microns.
        self.left_bcd = builder.aIn(pv_name("BCD:L"), PREC=2, EGU="um")
        self.right_bcd = builder.aIn(pv_name("BCD:R"), PREC=2, EGU="um")

        self.current_offset = builder.aIn(pv_name("OFFSET"), EGU="um", PREC=2)
        self.current_angle = builder.aIn(pv_name("ANGLE"), EGU="u rad", PREC=2)

    def check_enabled(self, pv, value):
        return self.parent.check_enabled()

    # Coordinate conversion.  We're converting between centre oriented
    # coordinates (offset and angle) and end-point coordinates (two end points),
    # and the conversion is parameterised by the length (self.length) and the
    # fractional position of the centre (self.centre).  The figure below shows
    # the coordinate framework (the two / characters represent the line of a
    # diagonal beam joining the three + characters, and t is the angle of this
    # line from horizontal):
    #
    #      k*l
    #   |<----->|       |       Let a, b be end point positions (left, right)
    #   |       |       + b     Let c be the centre position, t the line angle
    #   |       |   /   |       Let l be the distance between end points
    # c---------+---------      Let k be the fractional centre position
    #   |   /t          |
    # a +   __          |       Define d = t * l, then b = a + d, c = a + k*d
    #   |<----- l ----->|
    #
    # Then it's easy to determine the following equations:
    #
    #   a = c - k * d           c = (1 - k) * a + k * b
    #   b = c + (1 - k) * d     d = b - a
    #
    # We work with all lengths in micrometres, so requiring scaling by 1e3 when
    # talking to the BPM in mm.  By fortunate coincidence length in m multiplied
    # by angle in microradians produces d in units of um.
    def bcd_to_coord(self, left, right):
        return (
            (1 - self.centre) * left + self.centre * right,
            (right - left) / self.length,
        )

    def coord_to_bcd(self, offset, angle):
        return (
            offset - self.centre * self.length * angle,
            offset + (1 - self.centre) * self.length * angle,
        )

    # Computes min and max offset and angle permissible in light of the current
    # settings.  From equations for a and be above we get constraint equations
    # (writing M for min/max a, b value):
    #
    #   a = c - k d =>
    #       k d - M          <= c <= k d + M
    #       (c - M) / k      <= d <= (c + M) / k
    #   b = c + (1-k) d =>
    #       -(1-k) d - M     <= c <= -(1-k) d + M
    #       (-c - M) / (1-k) <= d <= (-c + M) / (1-k)
    def compute_limits(self, offset, angle):
        l = self.length
        c = offset
        d = angle * l
        k = self.centre
        M = bcd_limit.get()

        return (
            max(k * d, -(1 - k) * d) - M,  # Min offset
            min(k * d, -(1 - k) * d) + M,  # Max offset
            max((c - M) / k, (-c - M) / (1 - k)) / l,  # Min angle
            min((c + M) / k, (-c + M) / (1 - k)) / l,
        )  # Max angle

    def severity(self, min_val, max_val):
        if min_val < max_val:
            return (alarm.NO_ALARM,)
        elif min_val == max_val:
            return (alarm.MINOR_ALARM, alarm.HW_LIMIT_ALARM)
        else:
            return (alarm.MAJOR_ALARM, alarm.HW_LIMIT_ALARM)

    # Called when either BCD value changes.  Update offset and angle to reflect
    # the current BCD settings.
    def update_bcd(self):
        # Keep mirror values up to date
        self.left_bcd.set(self.left.value)
        self.right_bcd.set(self.right.value)

        # Convert current values back into offset and angle and update the
        # corresponding readback PVs.
        left, right = self.left.value, self.right.value
        offset, angle = self.bcd_to_coord(left, right)
        self.current_offset.set(offset)
        self.current_angle.set(angle)

        # Update the min and max limits accordingly.
        min_offset, max_offset, min_angle, max_angle = self.compute_limits(
            offset, angle
        )
        offset_sev = self.severity(min_offset, max_offset)
        angle_sev = self.severity(min_angle, max_angle)
        self.min_offset.set(min_offset, *offset_sev)
        self.max_offset.set(max_offset, *offset_sev)
        self.min_angle.set(min_angle, *angle_sev)
        self.max_angle.set(max_angle, *angle_sev)

    # Computes end point coordinates from angle and offset and sets end points
    # accordingly after trimming to fit within acceptable bounds.
    def set_target(self, value):
        offset = self.target_offset.get()
        angle = self.target_angle.get()
        a, b = self.coord_to_bcd(offset, angle)
        a, b = constrain_bcd(a, b)
        self.left.put(a)
        self.right.put(b)

    # This call will refresh the displayed control limits for all axes.
    @classmethod
    def refresh_all_limits(cls, _):
        for axis in cls.all_axes:
            axis.update_bcd()


# A single BCD control is a pair of axes X & Y.
class BCD:
    def __init__(self, name, right_id, length, centre):
        self.name = name  # To help with live debugging if necessary

        # Use BPM id of downstream BPM to compute BPM name and upstream BPM.
        left_id = right_id - 1
        if left_id == 0:
            left_id = bpm_list.BPM_count
        left = bpm_list.BPMS[left_id - 1]
        right = bpm_list.BPMS[right_id - 1]

        builder.SetDeviceName("SR-DI-%s-01" % name)
        self.enable_pv = builder.boolOut(
            "ENABLE_S", "Disabled", "Enabled", initial_value=True
        )
        self.x = Axis(self, "X", length, centre, left, right)
        self.y = Axis(self, "Y", length, centre, left, right)

    def check_enabled(self):
        return self.enable_pv.get()


# Create BCD controller for each straight.
def create_bcds():
    def default_length(n):
        if (n - 1) % 4 == 0:
            return BCD_LONG_LENGTH
        else:
            return BCD_SHORT_LENGTH

    # Creates a BCD controller named with given prefix.  The suffix is used to
    # identify the downstream BPM for the straight, this is C for most straights
    # and S for the two special straights in cells 9 and 13.
    def create_bcd(n, prefix, suffix, id=1):
        name = "%s%02d" % (prefix, n)
        bpm_id = bpm_list.BPM_name_id["SR%02d%s-DI-EBPM-%02d" % (n, suffix, id)]
        length = BCD_SPECIAL_LENGTHS.get(name, default_length(n))
        centre = BCD_SPECIAL_CENTRES.get(name, 0.5)
        bcds.append(BCD(name, bpm_id, length, centre))

    bcds = []
    for n in range(1, 25):
        if n in (9, 13):
            # Both straights 9 and 13 have an upstream I straight and a
            # downstream J straight
            create_bcd(n, "I", "S")
            create_bcd(n, "J", "C")
        else:
            # Normal straights are named I and end at a C-1 BPM.
            create_bcd(n, "I", "C")
            if n == 2:
                # Special second straight for J2
                create_bcd(n, "J", "C", 5)
    return bcds


# Define these as globals for now for simplicity
bcd_limit = None
slew_rate = None
bcds = None


def setup_bcd(device_name="SR-DI-EBPM-01"):
    """Create BCD controllers and related PVs."""
    global bcd_limit, slew_rate, bcds

    builder.SetDeviceName(device_name)
    bcd_limit = builder.aOut(
        "BCD_LIMIT",
        0,
        1000,
        EGU="um",
        initial_value=BCD_LIMIT,
        on_update=Axis.refresh_all_limits,
    )
    slew_rate = builder.aOut("SLEW_RATE", EGU="um/s", initial_value=BCD_SLEW_RATE)

    # We hang onto the created BCD instances for debugging in case we decide to do
    # some poking about in the live system!
    bcds = create_bcds()
    return {"bcds": bcds}
