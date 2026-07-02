# Copyright (c) 2023-2026 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""ANTA MCP server."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from anta import __DEBUG__

if TYPE_CHECKING:
    from collections.abc import Callable

try:
    from ._main import cli

except ImportError as exc:

    def build_cli(exception: ImportError) -> Callable[[], None]:
        """Build MCP CLI function using the caught exception."""

        def wrap() -> None:
            """Error message if any MCP dependency is missing."""
            if not exception.name or not (exception.name == "mcp" or exception.name.startswith("mcp.")):
                raise exception

            msg = (
                "The ANTA MCP server could not run because the required dependencies were not installed.\n"
                "Make sure you've installed everything with: pip install 'anta[mcp]'\n"
            )
            sys.stderr.write(msg)
            if __DEBUG__:
                sys.stderr.write(f"The caught exception was: {exception}\n")

            sys.exit(1)

        return wrap

    cli = build_cli(exc)

__all__ = ["cli"]

if __name__ == "__main__":
    cli()
