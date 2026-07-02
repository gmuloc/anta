# Copyright (c) 2023-2026 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""Safe ANTA MCP tool implementations."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import ValidationError
from yaml import YAMLError

from anta._runner import AntaRunContext, AntaRunFilters, AntaRunner
from anta.catalog import AntaCatalog
from anta.inventory import AntaInventory
from anta.inventory.exceptions import InventoryIncorrectSchemaError, InventoryRootKeyError
from anta.mcp.models import StoredRun
from anta.mcp.serializers import serialize_catalog, serialize_inventory, serialize_result, serialize_run_context
from anta.result_manager.models import AntaTestStatus

FileFormat = Literal["yaml", "json"]

DUMMY_USERNAME = "anta-mcp-validation"
DUMMY_PASSWORD = "anta-mcp-validation"
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 500


class RunStore:
    """In-memory MCP run store."""

    def __init__(self) -> None:
        self._runs: dict[str, StoredRun] = {}

    def add(self, context: AntaRunContext) -> StoredRun:
        """Store an ANTA run context."""
        run_id = uuid4().hex
        stored = StoredRun(run_id=run_id, context=context, created_at=datetime.now(tz=timezone.utc).isoformat())
        self._runs[run_id] = stored
        return stored

    def get(self, run_id: str) -> StoredRun:
        """Return a stored run."""
        try:
            return self._runs[run_id]
        except KeyError as exc:
            msg = f"Unknown ANTA MCP run_id: {run_id}"
            raise ValueError(msg) from exc

    def list(self) -> list[StoredRun]:
        """List stored runs."""
        return sorted(self._runs.values(), key=lambda run: run.created_at)

    def clear(self, run_id: str) -> bool:
        """Clear a stored run."""
        return self._runs.pop(run_id, None) is not None


RUN_STORE = RunStore()


def _error_response(message: str, exc: Exception | None = None) -> dict[str, Any]:
    """Return a consistent MCP error payload."""
    response: dict[str, Any] = {"valid": False, "error": message}
    if exc is not None:
        response["error_type"] = exc.__class__.__name__
        response["error_details"] = str(exc)
    return response


def _allowed_roots() -> list[Path]:
    """Return paths allowed for ANTA MCP file inputs."""
    raw_paths = [Path.cwd()]
    env_paths = os.environ.get("ANTA_MCP_ALLOWED_PATHS")
    if env_paths:
        raw_paths.extend(Path(path) for path in env_paths.split(os.pathsep) if path)
    return [path.expanduser().resolve() for path in raw_paths]


def _resolve_allowed_path(filename: str | Path) -> Path:
    """Resolve a user path and ensure it is under an allowed root."""
    path = Path(filename).expanduser().resolve()
    if not any(path == root or path.is_relative_to(root) for root in _allowed_roots()):
        allowed = ", ".join(str(root) for root in _allowed_roots())
        msg = f"Path '{path}' is outside ANTA MCP allowed roots: {allowed}"
        raise ValueError(msg)
    return path


def _parse_inventory(
    inventory_path: str | Path,
    *,
    file_format: FileFormat,
    username: str,
    password: str,
    enable_password: str | None = None,
    timeout: float | None = None,
    enable: bool = False,
    insecure: bool = False,
    disable_cache: bool = False,
) -> AntaInventory:
    """Parse an ANTA inventory after path validation."""
    return AntaInventory.parse(
        filename=_resolve_allowed_path(inventory_path),
        username=username,
        password=password,
        enable_password=enable_password,
        timeout=timeout,
        file_format=file_format,
        enable=enable,
        insecure=insecure,
        disable_cache=disable_cache,
    )


def _parse_catalog(catalog_path: str | Path, *, file_format: FileFormat) -> AntaCatalog:
    """Parse an ANTA catalog after path validation."""
    return AntaCatalog.parse(filename=_resolve_allowed_path(catalog_path), file_format=file_format)


def _credentials_from_env() -> tuple[str, str, str | None]:
    """Return ANTA credentials from environment variables."""
    username = os.environ.get("ANTA_USERNAME")
    password = os.environ.get("ANTA_PASSWORD")
    enable_password = os.environ.get("ANTA_ENABLE_PASSWORD")
    missing = [name for name, value in {"ANTA_USERNAME": username, "ANTA_PASSWORD": password}.items() if not value]
    if missing:
        msg = f"Missing required environment variable(s): {', '.join(missing)}"
        raise ValueError(msg)
    if username is None or password is None:
        msg = "Missing required ANTA credentials"
        raise ValueError(msg)
    return username, password, enable_password


def _normalize_filter(values: list[str] | None) -> set[str] | None:
    """Normalize optional MCP list arguments to runner filters."""
    return set(values) if values else None


def _normalize_status_filter(status: list[str] | None) -> set[AntaTestStatus] | None:
    """Normalize optional status filter values."""
    if not status:
        return None
    try:
        return {AntaTestStatus(value) for value in status}
    except ValueError as exc:
        allowed = ", ".join(item.value for item in AntaTestStatus)
        msg = f"Invalid status filter. Accepted values are: {allowed}"
        raise ValueError(msg) from exc


def _page_bounds(offset: int, limit: int) -> tuple[int, int]:
    """Return sanitized pagination bounds."""
    safe_offset = max(offset, 0)
    safe_limit = min(max(limit, 1), MAX_PAGE_LIMIT)
    return safe_offset, safe_limit


def anta_validate_inventory(inventory_path: str, file_format: FileFormat = "yaml") -> dict[str, Any]:
    """Parse an ANTA inventory file and return metadata without connecting to devices."""
    try:
        inventory = _parse_inventory(
            inventory_path,
            file_format=file_format,
            username=DUMMY_USERNAME,
            password=DUMMY_PASSWORD,
            disable_cache=True,
        )
    except (TypeError, ValueError, YAMLError, OSError, ValidationError, InventoryIncorrectSchemaError, InventoryRootKeyError) as exc:
        return _error_response(f"Failed to validate inventory '{inventory_path}'", exc)
    return serialize_inventory(inventory)


def anta_validate_catalog(catalog_path: str, file_format: FileFormat = "yaml") -> dict[str, Any]:
    """Parse an ANTA catalog file and return test metadata."""
    try:
        catalog = _parse_catalog(catalog_path, file_format=file_format)
    except (TypeError, ValueError, YAMLError, OSError, ValidationError) as exc:
        return _error_response(f"Failed to validate catalog '{catalog_path}'", exc)
    return serialize_catalog(catalog)


async def anta_plan_nrfu_run(
    inventory_path: str,
    catalog_path: str,
    inventory_format: FileFormat = "yaml",
    catalog_format: FileFormat = "yaml",
    tags: list[str] | None = None,
    devices: list[str] | None = None,
    tests: list[str] | None = None,
    timeout: float | None = None,
    enable: bool = False,
    insecure: bool = False,
    disable_cache: bool = True,
) -> dict[str, Any]:
    """Plan an ANTA NRFU run without connecting to devices or executing tests."""
    try:
        inventory = _parse_inventory(
            inventory_path,
            file_format=inventory_format,
            username=DUMMY_USERNAME,
            password=DUMMY_PASSWORD,
            timeout=timeout,
            enable=enable,
            insecure=insecure,
            disable_cache=disable_cache,
        )
        catalog = _parse_catalog(catalog_path, file_format=catalog_format)
        filters = AntaRunFilters(devices=_normalize_filter(devices), tests=_normalize_filter(tests), tags=_normalize_filter(tags))
        context = await AntaRunner().run(inventory=inventory, catalog=catalog, filters=filters, dry_run=True)
    except (TypeError, ValueError, YAMLError, OSError, ValidationError, InventoryIncorrectSchemaError, InventoryRootKeyError) as exc:
        return _error_response("Failed to plan ANTA NRFU run", exc)
    return {"valid": True, **serialize_run_context(context)}


async def anta_run_nrfu(
    inventory_path: str,
    catalog_path: str,
    inventory_format: FileFormat = "yaml",
    catalog_format: FileFormat = "yaml",
    tags: list[str] | None = None,
    devices: list[str] | None = None,
    tests: list[str] | None = None,
    timeout: float | None = None,
    enable: bool = False,
    insecure: bool = False,
    disable_cache: bool = False,
    include_atomic: bool = False,
    offset: int = 0,
    limit: int = DEFAULT_PAGE_LIMIT,
) -> dict[str, Any]:
    """Run ANTA NRFU tests and store results for later pagination."""
    try:
        username, password, enable_password = _credentials_from_env()
        inventory = _parse_inventory(
            inventory_path,
            file_format=inventory_format,
            username=username,
            password=password,
            enable_password=enable_password,
            timeout=timeout,
            enable=enable,
            insecure=insecure,
            disable_cache=disable_cache,
        )
        catalog = _parse_catalog(catalog_path, file_format=catalog_format)
        filters = AntaRunFilters(devices=_normalize_filter(devices), tests=_normalize_filter(tests), tags=_normalize_filter(tags))
        context = await AntaRunner().run(inventory=inventory, catalog=catalog, filters=filters)
        stored_run = RUN_STORE.add(context)
    except (TypeError, ValueError, YAMLError, OSError, ValidationError, InventoryIncorrectSchemaError, InventoryRootKeyError) as exc:
        return _error_response("Failed to run ANTA NRFU tests", exc)

    return {
        "valid": True,
        **serialize_run_context(context, run_id=stored_run.run_id),
        "results_page": _results_page(stored_run, status=None, device=None, test=None, category=None, include_atomic=include_atomic, offset=offset, limit=limit),
    }


def anta_get_nrfu_results(
    run_id: str,
    status: list[str] | None = None,
    device: str | None = None,
    test: str | None = None,
    category: str | None = None,
    include_atomic: bool = False,
    offset: int = 0,
    limit: int = DEFAULT_PAGE_LIMIT,
) -> dict[str, Any]:
    """Return a filtered and paginated page of results for a stored ANTA run."""
    try:
        stored_run = RUN_STORE.get(run_id)
        status_filter = _normalize_status_filter(status)
    except ValueError as exc:
        return _error_response("Failed to get ANTA NRFU results", exc)
    return {
        "valid": True,
        "run_id": run_id,
        "results_page": _results_page(
            stored_run,
            status=status_filter,
            device=device,
            test=test,
            category=category,
            include_atomic=include_atomic,
            offset=offset,
            limit=limit,
        ),
    }


def anta_list_runs() -> dict[str, Any]:
    """List ANTA runs stored in the MCP process."""
    runs = [
        {
            "run_id": stored_run.run_id,
            "created_at": stored_run.created_at,
            **serialize_run_context(stored_run.context),
        }
        for stored_run in RUN_STORE.list()
    ]
    return {"valid": True, "run_count": len(runs), "runs": runs}


def anta_clear_run(run_id: str) -> dict[str, Any]:
    """Delete one stored ANTA run from MCP process memory."""
    cleared = RUN_STORE.clear(run_id)
    return {"valid": True, "run_id": run_id, "cleared": cleared}


def _results_page(
    stored_run: StoredRun,
    *,
    status: set[AntaTestStatus] | None,
    device: str | None,
    test: str | None,
    category: str | None,
    include_atomic: bool,
    offset: int,
    limit: int,
) -> dict[str, Any]:
    """Build a filtered result page."""
    safe_offset, safe_limit = _page_bounds(offset, limit)
    results = stored_run.context.manager.get_results(status=status, sort_by=["name", "categories", "test"])
    if device is not None:
        results = [result for result in results if result.name == device]
    if test is not None:
        results = [result for result in results if result.test == test]
    if category is not None:
        results = [result for result in results if category in result.categories]
    page = results[safe_offset : safe_offset + safe_limit]
    return {
        "offset": safe_offset,
        "limit": safe_limit,
        "total": len(results),
        "next_offset": safe_offset + safe_limit if safe_offset + safe_limit < len(results) else None,
        "results": [serialize_result(result, include_atomic=include_atomic) for result in page],
    }
