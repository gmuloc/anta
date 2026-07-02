# Copyright (c) 2023-2026 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""ANTA MCP server CLI."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

from anta import __DEBUG__
from anta.logger import Log
from anta.mcp.server import run_server

if TYPE_CHECKING:
    from anta.logger import LogLevel


def _build_parser() -> argparse.ArgumentParser:
    """Build the ANTA MCP argument parser."""
    parser = argparse.ArgumentParser(description="Arista Network Test Automation (ANTA) MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio"],
        default="stdio",
        help="MCP transport to use. Streamable HTTP will be added in a future release.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Send ANTA MCP logs to a file. Logs are never emitted on stdout when using stdio.",
    )
    parser.add_argument(
        "--log-level",
        choices=[level.value for level in Log],
        default=logging.getLevelName(logging.INFO),
        help="ANTA MCP logging level.",
    )
    return parser


def cli() -> None:
    """Entrypoint for the `anta-mcp` script."""
    parser = _build_parser()
    args = parser.parse_args()
    _setup_mcp_logging(cast("LogLevel", args.log_level), args.log_file)
    run_server(transport=args.transport)


def _setup_mcp_logging(level: LogLevel = Log.INFO, file: Path | None = None) -> None:
    """Configure logging without writing to stdout."""
    root = logging.getLogger()
    root.handlers.clear()

    loglevel = logging.DEBUG if __DEBUG__ else getattr(logging, level.upper())
    root.setLevel(loglevel)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    if file is not None:
        file_handler = logging.FileHandler(file)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    if loglevel == logging.INFO:
        logging.getLogger("asyncssh").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    """Entrypoint for python module execution."""
    try:
        cli()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
