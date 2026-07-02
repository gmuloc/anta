# Copyright (c) 2023-2026 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""MCP server construction for ANTA."""

from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import FastMCP

from anta.mcp.tools import (
    anta_clear_run,
    anta_get_nrfu_results,
    anta_list_runs,
    anta_plan_nrfu_run,
    anta_run_nrfu,
    anta_validate_catalog,
    anta_validate_inventory,
)


def build_server() -> FastMCP:
    """Build and return the ANTA MCP server."""
    server = FastMCP("ANTA")
    server.tool()(anta_validate_inventory)
    server.tool()(anta_validate_catalog)
    server.tool()(anta_plan_nrfu_run)
    server.tool()(anta_run_nrfu)
    server.tool()(anta_get_nrfu_results)
    server.tool()(anta_list_runs)
    server.tool()(anta_clear_run)
    return server


def run_server(*, transport: Literal["stdio"] = "stdio") -> None:
    """Run the ANTA MCP server."""
    server = build_server()
    server.run(transport=transport)
