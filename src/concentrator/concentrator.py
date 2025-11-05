"""Diagnostics Storage Ring EBPM Concentrator."""

import os

from softioc import builder, softioc


def start_concentrator():
    """Start the concentrator IOC."""
    # A couple of identification PVs
    builder.SetDeviceName("CS-DI-IOC-01")
    builder.stringIn("WHOAMI", initial_value="Diagnostics Concentrator")
    builder.stringIn("HOSTNAME", initial_value=os.uname()[1])

    builder.Action("RESTART", on_update=softioc.epicsExit)

    from softioc import pvlog

    import concentrator.attenuation as attenuation
    import concentrator.autocurrent as autocurrent
    import concentrator.bcd as bcd
    import concentrator.booster as booster
    import concentrator.enabled as enabled
    import concentrator.injection as injection
    import concentrator.interlock as interlock
    import concentrator.maxadc as maxadc
    import concentrator.sr as sr
    import concentrator.updater as updater

    # 1) Core health/enable state
    enabled.setup()

    # 2) Common updaters; capture the attenuation updater
    updaters = updater.setup()
    atten_updater = updaters["AttenUpdater"]

    # 3) Attenuation control (needs the updater)
    atten = attenuation.setup(atten_updater=atten_updater)

    # 4) MaxADC and related waveforms (hook attenuation auto logic)
    maxadc.setup(on_maxadc_update=atten.UpdateMaxAdc)

    # 5) Auto current scaling (needs maxadc.current created)
    autocurrent.setup()

    # 6) BCD
    bcd.setup_bcd()

    # 7) Booster, EVR, Interlocks, Injection
    booster.setup()
    sr.setup()
    interlock.setup()
    injection.setup()

    builder.LoadDatabase()
    softioc.iocInit()
    softioc.interactive_ioc(globals())
