# Copyright (c) 2023-2025 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""Models related to anta.result_manager module."""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import polars as pl
from pydantic import BaseModel, Field

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


class AntaTestStatus(str, Enum):
    """Test status Enum for the TestResult.

    NOTE: This could be updated to StrEnum when Python 3.11 is the minimum supported version in ANTA.
    """

    UNSET = "unset"
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    SKIPPED = "skipped"

    @override
    def __str__(self) -> str:
        """Override the __str__ method to return the value of the Enum, mimicking the behavior of StrEnum."""
        return self.value


class BaseTestResult(BaseModel, ABC):
    """Base model for test results."""

    @abstractmethod
    def _set_status(self, status: AntaTestStatus, message: str | None = None) -> None:
        pass

    def is_success(self, message: str | None = None) -> None:
        """Set status to success.

        Parameters
        ----------
        message
            Optional message related to the test.

        """
        self._set_status(AntaTestStatus.SUCCESS, message)

    def is_failure(self, message: str | None = None) -> None:
        """Set status to failure.

        Parameters
        ----------
        message
            Optional message related to the test.

        """
        self._set_status(AntaTestStatus.FAILURE, message)

    def is_skipped(self, message: str | None = None) -> None:
        """Set status to skipped.

        Parameters
        ----------
        message
            Optional message related to the test.

        """
        self._set_status(AntaTestStatus.SKIPPED, message)

    def is_error(self, message: str | None = None) -> None:
        """Set status to error.

        Parameters
        ----------
        message
            Optional message related to the test.

        """
        self._set_status(AntaTestStatus.ERROR, message)


class AtomicTestResult(BaseTestResult):
    """Describe the result of an atomic test part of a larger test related to a TestResult instance.

    Attributes
    ----------
    parent : TestResult
    description : str
        Description of the AtomicTestResult.
    result : AntaTestStatus
        Result of the atomic test.
    messages : list[str]
        Messages reported by the test.
    """

    description: str
    result: AntaTestStatus = AntaTestStatus.UNSET
    messages: list[str] = []
    parent: TestResult = Field(exclude=True, repr=False)

    def model_post_init(self, _context: Any, /) -> None:  # noqa: ANN401
        """Call _set_status on post-init.

        If multiple messages are used to initialize, add them all one by one.
        """
        for message in self.messages:
            self.parent.messages.append(f"{self.description} - {message}")
        self._set_status(self.result)

    def _set_status(self, status: AntaTestStatus, message: str | None = None) -> None:
        """Set status and insert optional message.

        If the parent TestResult status is UNSET and this AtomicTestResult status is SUCCESS, the parent TestResult status will be set as a SUCCESS.
        If this AtomicTestResult status is FAILURE or ERROR, the parent TestResult status will be set with the same status.

        Parameters
        ----------
        status
            Status of the test.
        message
            Optional message.
        """
        self.result = status
        if (self.parent.result == AntaTestStatus.UNSET and status == AntaTestStatus.SUCCESS) or status in [AntaTestStatus.FAILURE, AntaTestStatus.ERROR]:
            self.parent.result = status
        if message is not None:
            self.messages.append(message)
            self.parent.messages.append(f"{self.description} - {message}")


class TestResult(BaseTestResult):
    """Describe the result of a test from a single device.

    Attributes
    ----------
    name : str
        Name of the device on which the test was run.
    test : str
        Name of the AntaTest subclass.
    categories : list[str]
        List of categories the TestResult belongs to. Defaults to the AntaTest subclass categories.
    description : str
        Description of the TestResult. Defaults to the AntaTest subclass description.
    result : AntaTestStatus
        Result of the test.
    messages : list[str]
        Messages reported by the test.
    atomic_results: list[AtomicTestResult]
        A list of AtomicTestResult instances which can be used to store atomic results during the test execution.
        These are used to generate a detailed breakdown in the final report, supplementing the global TestResult.
    custom_field : str | None
        Custom field to store a string for flexibility in integrating with ANTA.
    """

    name: str
    test: str
    categories: list[str]
    description: str
    result: AntaTestStatus = AntaTestStatus.UNSET
    messages: list[str] = []
    atomic_results: list[AtomicTestResult] = []
    custom_field: str | None = None

    @override
    def __str__(self) -> str:
        """Return a human readable string of this TestResult."""
        results = f"{self.result} [{','.join([str(r.result) for r in self.atomic_results])}]" if self.atomic_results else str(self.result)
        lines = "\n".join(self.messages)
        messages = f"\nMessages:\n{lines}" if self.messages else ""
        return f"Test {self.test} (on {self.name}): {results}{messages}"

    def add(self, description: str, status: AntaTestStatus = AntaTestStatus.UNSET, messages: list[str] | None = None) -> AtomicTestResult:
        """Create and add a new AtomicTestResult to this TestResult instance.

        Parameters
        ----------
        description
            Description of the AtomicTestResult.
        status
            Status of the AtomicTestResult.
        messages
            Optional list of messages when initializing the AtomicTestResult.
        """
        messages = messages or []
        res = AtomicTestResult(description=description, parent=self, result=status, messages=messages)
        self.atomic_results.append(res)
        return res

    @override
    def _set_status(self, status: AntaTestStatus, message: str | None = None) -> None:
        """Set status and insert optional message.

        Parameters
        ----------
        status
            Status of the test.
        message
            Optional message.
        """
        self.result = status
        if message is not None:
            self.messages.append(message)

    @classmethod
    def rebuild_from_df(cls, data_dict: dict[str, Any]) -> TestResult:
        """Rebuild a TestResult instance from the data dict retrieved from polar."""
        atomic_results_dicts = data_dict.pop("atomic_results", None)
        test_result = cls.model_construct(**data_dict)
        if atomic_results_dicts:
            test_result.atomic_results = [AtomicTestResult(parent=test_result, **atomic_res_dict) for atomic_res_dict in atomic_results_dicts]
        return test_result


# Stats
_STATUS_VALUES = ["unset", "success", "failure", "error", "skipped"]
FAILURE_STATUSES = [AntaTestStatus.FAILURE, AntaTestStatus.ERROR]
BASE_AGG_EXPRESSIONS = [(pl.col("result") == status).sum().alias(f"tests_{status}_count") for status in _STATUS_VALUES]


@dataclass
class DeviceStats:
    """Device statistics for a run of tests."""

    tests_success_count: int = 0
    tests_skipped_count: int = 0
    tests_failure_count: int = 0
    tests_error_count: int = 0
    tests_unset_count: int = 0
    tests_failure: set[str] = field(default_factory=set)
    categories_failed: set[str] = field(default_factory=set)
    categories_skipped: set[str] = field(default_factory=set)

    @classmethod
    def from_polars_dict(cls, d: dict[str, Any]) -> DeviceStats:
        """Instantiate DeviceStats from a dictionary produced by Polars aggregation."""
        kwargs: dict[str, Any] = _map_polars_counts(d, "tests_")

        kwargs["categories_failed"] = set(d.get("categories_failed", []))
        kwargs["categories_skipped"] = set(d.get("categories_skipped", []))
        kwargs["tests_failure"] = set(d.get("tests_failure", []))

        return cls(**kwargs)

    @staticmethod
    def _get_agg_expressions() -> list[pl.Expr]:
        """Return the complete Polars expressions for DeviceStats."""
        agg_exprs = BASE_AGG_EXPRESSIONS[:]
        agg_exprs.extend(
            [
                _aggregate_unique_list_elements("categories", pl.col("result") == AntaTestStatus.SKIPPED).alias("categories_skipped"),
                _aggregate_unique_list_elements("categories", pl.col("result").is_in(FAILURE_STATUSES)).alias("categories_failed"),
                pl.col("test").filter(pl.col("result").is_in(FAILURE_STATUSES)).unique().alias("tests_failure"),
            ]
        )
        return agg_exprs


@dataclass
class CategoryStats:
    """Category statistics for a run of tests."""

    tests_success_count: int = 0
    tests_skipped_count: int = 0
    tests_failure_count: int = 0
    tests_error_count: int = 0
    tests_unset_count: int = 0

    @classmethod
    def from_polars_dict(cls, d: dict[str, Any]) -> CategoryStats:
        """Instantiate CategoryStats from a dictionary produced by Polars aggregation."""
        kwargs = _map_polars_counts(d, "tests_")
        return cls(**kwargs)

    @staticmethod
    def _get_agg_expressions() -> list[pl.Expr]:
        """Return the complete Polars expressions for CategoryStats."""
        return BASE_AGG_EXPRESSIONS[:]


@dataclass
class TestStats:
    """Test statistics for a run of tests."""

    devices_success_count: int = 0
    devices_skipped_count: int = 0
    devices_failure_count: int = 0
    devices_error_count: int = 0
    devices_unset_count: int = 0
    devices_failure: set[str] = field(default_factory=set)

    @classmethod
    def from_polars_dict(cls, d: dict[str, Any]) -> TestStats:
        """Instantiate TestStats from a dictionary produced by Polars aggregation."""
        kwargs: dict[str, Any] = _map_polars_counts(d, "devices_")

        kwargs["devices_failure"] = set(d.get("devices_failure", []))

        return cls(**kwargs)

    @staticmethod
    def _get_agg_expressions() -> list[pl.Expr]:
        """Return the complete Polars expressions for TestStats."""
        agg_exprs = BASE_AGG_EXPRESSIONS[:]
        agg_exprs.append(pl.col("name").filter(pl.col("result").is_in(FAILURE_STATUSES)).unique().alias("devices_failure"))
        return agg_exprs


def _map_polars_counts(d: dict[str, Any], prefix: str) -> dict[str, int]:
    """Map standard Polars counts to dataclass kwargs."""
    kwargs = {}
    for status in AntaTestStatus:
        input_key = f"tests_{status.value}_count"
        output_key = f"{prefix}{status.value.lower()}_count"
        kwargs[output_key] = d.get(input_key, 0)
    return kwargs


def _aggregate_unique_list_elements(col: str, status_expr: pl.Expr) -> pl.Expr:
    """Encapsulate the complex Polars logic for aggregating unique list elements."""
    return pl.col(col).filter(status_expr).explode().unique().implode()
