# Copyright (c) 2023-2026 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""Serialization helpers for the ANTA MCP server."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from anta import __version__ as anta_version
from anta.result_manager.models import AntaTestStatus, TestResult

if TYPE_CHECKING:
    from anta._runner import AntaRunContext
    from anta.catalog import AntaCatalog
    from anta.inventory import AntaInventory


def json_safe(value: Any) -> Any:  # noqa: ANN401
    """Return a JSON-safe representation for common ANTA objects."""
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, timedelta):
        return value.total_seconds()
    if is_dataclass(value) and not isinstance(value, type):
        return {key: json_safe(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def serialize_inventory(inventory: AntaInventory) -> dict[str, Any]:
    """Serialize inventory metadata without credentials."""
    devices = [
        {
            "name": device.name,
            "host": getattr(device, "host", device.name),
            "port": getattr(device, "port", None),
            "tags": sorted(device.tags),
            "disable_cache": device.cache is None,
        }
        for device in inventory.devices
    ]
    tags = sorted({tag for device in inventory.devices for tag in device.tags})
    return {
        "valid": True,
        "device_count": len(devices),
        "tags": tags,
        "devices": devices,
        "max_potential_connections": inventory.max_potential_connections,
    }


def serialize_catalog(catalog: AntaCatalog) -> dict[str, Any]:
    """Serialize catalog metadata."""
    tests = [
        {
            "name": test_definition.test.name,
            "module": test_definition.test.__module__,
            "categories": test_definition.test.categories,
            "tags": sorted(test_definition.inputs.filters.tags) if test_definition.inputs.filters and test_definition.inputs.filters.tags else [],
        }
        for test_definition in catalog.tests
    ]
    return {
        "valid": True,
        "test_count": len(tests),
        "modules": sorted({test["module"] for test in tests}),
        "categories": sorted({category for test in tests for category in test["categories"]}),
        "tags": sorted({tag for test in tests for tag in test["tags"]}),
        "tests": tests,
    }


def serialize_result(result: TestResult, *, include_atomic: bool = False) -> dict[str, Any]:
    """Serialize a single ANTA test result."""
    data = result.model_dump(mode="json", exclude={"atomic_results"} if not include_atomic else None)
    return json_safe(data)


def serialize_run_context(ctx: AntaRunContext, *, run_id: str | None = None) -> dict[str, Any]:
    """Serialize an ANTA run context summary."""
    active_filters: dict[str, list[str]] = {}
    if ctx.filters.tags:
        active_filters["tags"] = sorted(ctx.filters.tags)
    if ctx.filters.tests:
        active_filters["tests"] = sorted(ctx.filters.tests)
    if ctx.filters.devices:
        active_filters["devices"] = sorted(ctx.filters.devices)

    status = ctx.manager.get_status()
    response: dict[str, Any] = {
        "anta_version": anta_version,
        "status": status,
        "error_status": ctx.manager.error_status,
        "exit_code_equivalent": exit_code_equivalent(status),
        "dry_run": ctx.dry_run,
        "start_time": ctx.start_time.isoformat() if ctx.start_time else None,
        "end_time": ctx.end_time.isoformat() if ctx.end_time else None,
        "duration_seconds": ctx.duration.total_seconds() if ctx.duration else None,
        "total_devices_in_inventory": ctx.total_devices_in_inventory,
        "total_devices_filtered_by_tags": ctx.total_devices_filtered_by_tags,
        "total_devices_unreachable": ctx.total_devices_unreachable,
        "total_devices_selected_for_testing": ctx.total_devices_selected_for_testing,
        "total_tests_scheduled": ctx.total_tests_scheduled,
        "total_results": len(ctx.manager),
        "devices_filtered_at_setup": ctx.devices_filtered_at_setup,
        "devices_unreachable_at_setup": ctx.devices_unreachable_at_setup,
        "warnings_at_setup": ctx.warnings_at_setup,
        "filters_applied": active_filters or None,
        "selected_devices": sorted(ctx.selected_inventory.keys()),
        "selected_tests_by_device": {
            device.name: sorted(test_definition.test.name for test_definition in test_definitions) for device, test_definitions in ctx.selected_tests.items()
        },
        "result_counts": {status.value: ctx.manager.get_total_results({status}) for status in AntaTestStatus},
    }
    if run_id is not None:
        response["run_id"] = run_id
    return json_safe(response)


def exit_code_equivalent(status: str) -> int:
    """Return the ANTA CLI exit-code equivalent for a result status."""
    if status in {"unset", "skipped", "success"}:
        return 0
    if status == "failure":
        return 4
    if status == "error":
        return 3
    return 1
