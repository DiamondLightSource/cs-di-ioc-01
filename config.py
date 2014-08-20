# Simple concentrator configuration definitions.
# Everything here is read from the concentrator configuration file, normally
# found in /home/ops/diagnostics/concentrator/concentrator.config

import sys
import os
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
    CONFIG_FILE = '/home/ops/diagnostics/config/CS-DI-IOC-01.config'

# We start with a default configuration dictionary which is then overwritten
# with settings loaded from target configuration file.
config_dir = dict(
    # Use local copy of FA ids file to avoid accidents if the configured file is
    # changed.  This should be a faithful copy of the file stored in
    #   /home/ops/diagnostics/config/CS-DI-IOC-01.config
    BPM_list_file = os.path.join(os.path.dirname(__file__), 'fa-ids.sr')
)
execfile(CONFIG_FILE, {}, config_dir)

__all__ = config_dir.keys()
globals().update(config_dir)
