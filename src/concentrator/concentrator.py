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

    builder.LoadDatabase()
    softioc.iocInit()
    softioc.interactive_ioc(globals())
