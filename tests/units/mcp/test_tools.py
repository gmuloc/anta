# Copyright (c) 2023-2026 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""Tests for anta.mcp.tools."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from anta._runner import AntaRunner
from anta.catalog import AntaCatalog
from anta.inventory import AntaInventory
from anta.mcp.tools import (
    RUN_STORE,
    anta_clear_run,
    anta_get_nrfu_results,
    anta_list_runs,
    anta_plan_nrfu_run,
    anta_run_nrfu,
    anta_validate_catalog,
    anta_validate_inventory,
)

if TYPE_CHECKING:
    import pytest

DATA_DIR: Path = Path(__file__).parent.parent.parent / "data"


def test_validate_inventory() -> None:
    """Test inventory validation tool."""
    response = anta_validate_inventory(str(DATA_DIR / "test_inventory_with_tags.yml"))

    assert response["valid"] is True
    assert response["device_count"] == 3
    assert "leaf" in response["tags"]
    assert {device["name"] for device in response["devices"]} == {"leaf1", "leaf2", "spine1"}


def test_validate_catalog() -> None:
    """Test catalog validation tool."""
    response = anta_validate_catalog(str(DATA_DIR / "test_catalog_with_tags.yml"))

    assert response["valid"] is True
    assert response["test_count"] == 11
    assert "system" in response["categories"]
    assert "leaf" in response["tags"]


def test_validate_path_outside_allowed_roots(tmp_path: Path) -> None:
    """Test path allowlist rejection."""
    inventory = tmp_path / "inventory.yml"
    inventory.write_text("anta_inventory: {}\n", encoding="utf-8")

    response = anta_validate_inventory(str(inventory))

    assert response["valid"] is False
    assert "outside ANTA MCP allowed roots" in response["error_details"]


async def test_plan_nrfu_run() -> None:
    """Test NRFU dry-run planning."""
    response = await anta_plan_nrfu_run(
        str(DATA_DIR / "test_inventory_with_tags.yml"),
        str(DATA_DIR / "test_catalog_with_tags.yml"),
        tags=["leaf"],
    )

    assert response["valid"] is True
    assert response["dry_run"] is True
    assert response["total_devices_selected_for_testing"] == 2
    assert response["total_tests_scheduled"] == 6
    assert response["selected_devices"] == ["leaf1", "leaf2"]


async def test_run_nrfu_missing_credentials(setenvvar: pytest.MonkeyPatch) -> None:  # noqa: ARG001
    """Test NRFU execution requires credentials from environment variables."""
    response = await anta_run_nrfu(str(DATA_DIR / "test_inventory_with_tags.yml"), str(DATA_DIR / "test_catalog_with_tags.yml"))

    assert response["valid"] is False
    assert "ANTA_USERNAME" in response["error_details"]
    assert "ANTA_PASSWORD" in response["error_details"]


async def test_result_store_pagination() -> None:
    """Test listing, paging, filtering, and clearing stored run results."""
    inventory = AntaInventory.parse(filename=DATA_DIR / "test_inventory_with_tags.yml", username="anta", password="anta")
    catalog = AntaCatalog.parse(filename=DATA_DIR / "test_catalog_with_tags.yml")
    context = await AntaRunner().run(inventory, catalog, dry_run=True)
    stored_run = RUN_STORE.add(context)

    page_response = anta_get_nrfu_results(stored_run.run_id, device="leaf1", offset=0, limit=2)
    assert page_response["valid"] is True
    assert page_response["results_page"]["limit"] == 2
    assert page_response["results_page"]["total"] == 9
    assert len(page_response["results_page"]["results"]) == 2

    list_response = anta_list_runs()
    assert list_response["valid"] is True
    assert stored_run.run_id in {run["run_id"] for run in list_response["runs"]}

    clear_response = anta_clear_run(stored_run.run_id)
    assert clear_response == {"valid": True, "run_id": stored_run.run_id, "cleared": True}
