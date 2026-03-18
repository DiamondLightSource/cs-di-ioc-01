"""Interface for ``python -m concentrator``."""

import os
from argparse import ArgumentParser
from collections.abc import Sequence

from . import __version__
from .concentrator import start_concentrator

__all__ = ["main"]


def main(args: Sequence[str] | None = None) -> None:
    """Argument parser for the CLI."""
    parser = ArgumentParser()
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=__version__,
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    parsed_args = parser.parse_args(args)

    if parsed_args.debug:
        os.environ["EPICS_CAS_SERVER_PORT"] = "6064"
    start_concentrator()


if __name__ == "__main__":
    main()
