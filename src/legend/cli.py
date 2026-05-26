import argparse
import os
import sys
from pathlib import Path

from legend.constants import LEGEND_MODEL_DIR_ENV
from legend.setup import ensure_models


def main() -> None:
    """Entry point for the legend CLI."""
    parser = argparse.ArgumentParser(
        prog="legend",
        description="Legend PII pseudonymization CLI.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "download-models",
        help="Download the spaCy model to the resolved model directory.",
    )

    args = parser.parse_args()

    if args.command == "download-models":
        env = os.environ.get(LEGEND_MODEL_DIR_ENV)
        path: Path | None = Path(env) if env else None
        ensure_models(path)
        sys.exit(0)
    else:
        parser.print_help()
        sys.exit(1)
