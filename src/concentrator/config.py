# Simple concentrator configuration definitions.
# Everything here is read from the concentrator configuration file, normally
# found in /home/ops/diagnostics/concentrator/concentrator.config


# CONFIG_FILE = "/home/ops/diagnostics/config/CS-DI-IOC-01.config"
CONFIG_FILE = "CS-DI-IOC-01.config"


def load(path: str = CONFIG_FILE) -> None:
    config_dir = {}
    exec(open(path).read(), {}, config_dir)
    globals().update(config_dir)
    global __all__
    __all__ = list(config_dir.keys())
