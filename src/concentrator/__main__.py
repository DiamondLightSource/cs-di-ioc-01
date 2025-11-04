"""Interface for ``python -m concentrator``."""

from argparse import ArgumentParser
from collections.abc import Sequence

from concentrator.concentrator import start_concentrator

from . import __version__

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
    parser.parse_args(args)

    start_concentrator()


if __name__ == "__main__":
    main()
