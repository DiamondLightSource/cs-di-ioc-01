# Simple concentrator configuration definitions.
# Everything here is read from the concentrator configuration file, normally
# found in /home/ops/diagnostics/concentrator/concentrator.config

import sys
if 'C' in sys.argv[1:]:
    CONFIG_FILE = 'CS-DI-IOC-01.config'
else:
    CONFIG_FILE = '/home/ops/diagnostics/concentrator/CS-DI-IOC-01.config'

config_dir = {}
execfile(CONFIG_FILE, {}, config_dir)

__all__ = config_dir.keys()
globals().update(config_dir)
