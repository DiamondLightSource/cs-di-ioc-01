import subprocess
import sys

from concentrator.concentrator import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "concentrator", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
