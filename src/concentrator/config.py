# Simple concentrator configuration definitions.
# Everything here is read from the concentrator configuration file, normally
# found in /home/ops/diagnostics/concentrator/concentrator.config


# CONFIG_FILE = "/home/ops/diagnostics/config/CS-DI-IOC-01.config"
CONFIG_FILE = "CS-DI-IOC-01.config"

config_dir = {}
exec(open(CONFIG_FILE).read(), {}, config_dir)

__all__ = list(config_dir.keys())
globals().update(config_dir)
