# Simple concentrator configuration definitions.
# Everything here is read from the concentrator configuration file, normally
# found in /home/ops/diagnostics/concentrator/concentrator.config

import sys
if 'C' in sys.argv[1:]:
    CONFIG_FILE = 'CS-DI-IOC-01.config'

    # Also hack caput
    class Fail:
        ok = False
        def __init__(self, name): self.name = name
    def caput(pvs, *args, **kargs):
        print 'caput', pvs, args, kargs
        if isinstance(pvs, str):
            return Fail(pvs)
        else:
            return map(Fail, pvs)

    from cothread import catools
    catools.caput = caput

else:
    CONFIG_FILE = '/home/ops/diagnostics/concentrator/CS-DI-IOC-01.config'

config_dir = {}
execfile(CONFIG_FILE, {}, config_dir)

__all__ = config_dir.keys()
globals().update(config_dir)
