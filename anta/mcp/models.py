# Copyright (c) 2023-2026 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""Models for the ANTA MCP server."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anta._runner import AntaRunContext


@dataclass
class StoredRun:
    """Process-local ANTA run stored for MCP pagination."""

    run_id: str
    context: AntaRunContext
    created_at: str
    results: list[dict[str, object]] = field(default_factory=list)
