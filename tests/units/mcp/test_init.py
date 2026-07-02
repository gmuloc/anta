# Copyright (c) 2023-2026 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""Tests for anta.mcp optional dependency handling."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import patch

import pytest

import anta as anta_module


@pytest.mark.skipif(sys.version_info <= (3, 11), reason="Unreliable behavior patching sys.modules before 3.11")
def test_mcp_error_missing_dependency(capsys: pytest.CaptureFixture[Any]) -> None:
    """Test ANTA MCP errors out when anta[mcp] was not installed."""
    with patch.dict(sys.modules, {"mcp": None}) as sys_modules:
        for key in list(sys_modules.keys()):
            if key.startswith(("anta.", "mcp.")):
                del sys_modules[key]
        if hasattr(anta_module, "mcp"):
            delattr(anta_module, "mcp")
        import anta.mcp

        with pytest.raises(SystemExit) as exc_info:
            anta.mcp.cli()

        captured = capsys.readouterr()
        assert "The ANTA MCP server could not run because the required dependencies were not installed." in captured.err
        assert "Make sure you've installed everything with: pip install 'anta[mcp]'" in captured.err
        assert exc_info.value.code == 1


@pytest.mark.skipif(sys.version_info <= (3, 11), reason="Unreliable behavior patching sys.modules before 3.11")
def test_mcp_error_missing_other_dependency() -> None:
    """Test ANTA MCP re-raises unrelated missing dependencies."""
    with patch.dict(sys.modules, {"pydantic": None}) as sys_modules:
        for key in list(sys_modules.keys()):
            if key.startswith("anta."):
                del sys_modules[key]
        if hasattr(anta_module, "mcp"):
            delattr(anta_module, "mcp")
        import anta.mcp

        with pytest.raises(ImportError, match="pydantic"):
            anta.mcp.cli()
