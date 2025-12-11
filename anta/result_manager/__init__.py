# Copyright (c) 2023-2025 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""Result Manager module for ANTA."""

from __future__ import annotations

import json
import logging
from functools import cached_property
from typing import Any, Literal

import polars as pl
from typing_extensions import deprecated

from anta.result_manager.models import AntaTestStatus, TestResult

from .models import CategoryStats, DeviceStats, TestStats

logger = logging.getLogger(__name__)


_STATUS_VALUES = ["unset", "success", "failure", "error", "skipped"]


class ResultManager:
    """Manager of ANTA Results.

    The status of the class is initialized to "unset"

    Then when adding a test with a status that is NOT 'error' the following
    table shows the updated status:

    | Current Status |         Added test Status       | Updated Status |
    | -------------- | ------------------------------- | -------------- |
    |      unset     |              Any                |       Any      |
    |     skipped    |         unset, skipped          |     skipped    |
    |     skipped    |            success              |     success    |
    |     skipped    |            failure              |     failure    |
    |     success    |     unset, skipped, success     |     success    |
    |     success    |            failure              |     failure    |
    |     failure    | unset, skipped success, failure |     failure    |

    If the status of the added test is error, the status is untouched and the
    `error_status` attribute is set to True.

    Attributes
    ----------
    results
    dump
    status
        Status rerpesenting all the results.
    error_status
        Will be `True` if a test returned an error.
    results_by_status
    dump
    json
    device_stats
    category_stats
    test_stats
    """

    # TODO: Remove the following pylint disable once deprecated methods are removed.
    # pylint: disable=too-many-public-methods

    def __init__(self) -> None:
        """Initialize a ResultManager instance."""
        self._results: list[TestResult] = []
        """buffer before putting the TestResult in df"""
        self.df: pl.DataFrame = pl.DataFrame()
        self.status: AntaTestStatus = AntaTestStatus.UNSET
        self.error_status: bool = False

    def add(self, result: TestResult) -> None:
        """Add a result to the ResultManager instance.

        The result is added to the internal list of results and the overall status
        of the ResultManager instance is updated based on the added test status.

        Parameters
        ----------
        result
            TestResult to add to the ResultManager instance.
        """
        self._results.append(result)
        self._update_status(result.result)

        # TODO: evaluate if we keep
        # Every time a new result is added, we need to clear the cached properties
        for name in ["results_by_status", "results_by_category"]:
            self.__dict__.pop(name, None)

    @classmethod
    def _from_df(cls, df: pl.DataFrame, status: AntaTestStatus, *, error_status: bool) -> ResultManager:
        """Private class method to instantiate a ResultManager directly from a Polars pl.DataFrame."""
        instance = cls()
        instance.df = df
        instance.status = status
        instance.error_status = error_status
        return instance

    def get_status(self, *, ignore_error: bool = False) -> str:
        """Return the current status including error_status if ignore_error is False."""
        return "error" if self.error_status and not ignore_error else self.status

    def reset(self) -> None:
        """Create or reset the attributes of the ResultManager instance."""
        self._results.clear()
        self.status = AntaTestStatus.UNSET
        self.error_status = False
        self.df = pl.DataFrame()

    def __len__(self) -> int:
        """Return the total number of collected results, including those in the buffer and those already finalized in the pl.DataFrame."""
        self.ensure_dataframe_is_ready()
        return self.df.height if self.df is not None else 0

    @property
    def results(self) -> list[TestResult]:
        """Get the complete list of TestResult objects by converting the internal Polars pl.DataFrame back to Pydantic models.

        Warning
        -------
            This is an expensive operation and should be avoided unless necessary.
        """
        self.ensure_dataframe_is_ready()

        if self.df is None or self.df.height == 0:
            return []

        return [TestResult.rebuild_from_df(d) for d in self.df.to_dicts()]

    @results.setter
    def results(self, value: list[TestResult]) -> None:
        """Set the list of TestResult, resetting the manager state first."""
        self.reset()

        for result in value:
            self.add(result)

    @property
    def dump(self) -> list[dict[str, Any]]:
        """Get a list of dictionary of the results by converting the internal Polars pl.DataFrame."""
        self.ensure_dataframe_is_ready()
        if self.df.height == 0:
            return []

        return self.df.to_dicts()

    @property
    def json(self) -> str:
        """Get a JSON representation of the results."""
        self.ensure_dataframe_is_ready()
        if self.df.height == 0:
            return "[]"

        return json.dumps(self.df.to_dicts(), indent=4)

    @property
    def device_stats(self) -> dict[str, DeviceStats]:
        """Get the device statistics calculated on demand from the Polars pl.DataFrame."""
        return self._map_stats_to_dataclass("name", DeviceStats)

    @property
    def category_stats(self) -> dict[str, CategoryStats]:
        """Get the category statistics calculated on demand from the Polars pl.DataFrame."""
        return self._map_stats_to_dataclass("categories", CategoryStats)

    @property
    def test_stats(self) -> dict[str, TestStats]:
        """Get the test statistics calculated on demand from the Polars pl.DataFrame."""
        return self._map_stats_to_dataclass("test", TestStats)

    @property
    @deprecated("This property is deprecated, use `category_stats` instead. This will be removed in ANTA v2.0.0.", category=DeprecationWarning)
    def sorted_category_stats(self) -> dict[str, CategoryStats]:
        """A property that returns the category_stats dictionary sorted by key name."""
        return self.category_stats

    def _get_results_dicts_by_status(self) -> dict[AntaTestStatus, list[dict[str, Any]]]:
        """Return results grouped by status as lists of dictionaries (Polars native speed)."""
        self.ensure_dataframe_is_ready()
        if self.df.height == 0:
            return {}

        results_dict: dict[AntaTestStatus, list[dict[str, Any]]] = {}

        for status_enum in AntaTestStatus:
            status_str = status_enum.value

            # Filter the main pl.DataFrame by status value
            df_group = self.df.filter(pl.col("result") == status_str)

            if df_group.height > 0:
                results_dict[status_enum] = df_group.to_dicts()

        return results_dict

    def _get_results_dicts_sorted_by_category(self) -> list[dict[str, Any]]:
        """Return all results sorted by category as a list of dictionaries (Polars native speed)."""
        self.ensure_dataframe_is_ready()

        if self.df.height == 0:
            return []

        # Sort the pl.DataFrame efficiently by the 'category' column
        sorted_df = self.df.sort("category")

        # Return the fast dictionary conversion
        return sorted_df.to_dicts()

    @cached_property
    def results_by_status(self) -> dict[AntaTestStatus, list[TestResult]]:
        """A cached property that returns the results grouped by status using Polars.

        Warning
        -------
            This operation incurs significant overhead due to conversion back to list[TestResult] objects.
        """
        dicts_by_status = self._get_results_dicts_by_status()
        return {status: [TestResult.rebuild_from_df(d) for d in dicts] for status, dicts in dicts_by_status.items()}

    @cached_property
    def results_by_category(self) -> list[TestResult]:
        """A cached property that returns the list of results sorted by categories using Polars.

        Warning
        -------
            This operation incurs significant overhead due to conversion back to list[TestResult] objects.
        """
        sorted_dicts = self._get_results_dicts_sorted_by_category()
        return [TestResult.rebuild_from_df(d) for d in sorted_dicts]

    def get_results(self, status: set[AntaTestStatus] | None = None, sort_by: list[str] | None = None) -> list[TestResult]:
        """Get the results, optionally filtered by status and sorted by TestResult fields.

        If no status is provided, all results are returned.

        Parameters
        ----------
        status
            Optional set of AntaTestStatus enum members to filter the results.
        sort_by
            Optional list of TestResult fields to sort the results.

        Returns
        -------
        list[TestResult]
            List of results.

        Warning
        -------
            This operation incurs significant overhead due to conversion back to list[TestResult] objects.
        """
        self.ensure_dataframe_is_ready()
        if self.df.height == 0:
            return []

        df_final = self.df

        # 2. Filtering by Status (Polars vectorized operation)
        if status is not None and len(status) > 0:
            status_values = [s.value for s in status]
            df_final = df_final.filter(pl.col("result").is_in(status_values))

        if sort_by:
            accepted_fields = TestResult.model_fields.keys()

            if not set(sort_by).issubset(set(accepted_fields)):
                msg = f"Invalid sort_by fields: {sort_by}. Accepted fields are: {list(accepted_fields)}"
                raise ValueError(msg)

            # Polars sorting expression to replicate Python's 'or ""' or 'or []' null handling
            # It handles List<String> (like categories) by filling nulls with an empty list,
            # and standard types by filling nulls with an empty string.
            sort_expressions = [
                pl.col(field).fill_null(pl.lit([]).cast(pl.List(pl.Utf8))) if field == "categories" else pl.col(field).fill_null(pl.lit("")) for field in sort_by
            ]

            df_final = df_final.sort(sort_expressions)

        return [TestResult.rebuild_from_df(d) for d in df_final.to_dicts()]

    def get_total_results(self, status: set[AntaTestStatus] | None = None) -> int:
        """Get the total number of results, optionally filtered by status.

        If no status is provided, the total number of results is returned.

        Parameters
        ----------
        status
            Optional set of AntaTestStatus enum members to filter the results.

        Returns
        -------
        int
            Total number of results.
        """
        self.ensure_dataframe_is_ready()
        if self.df.height == 0:
            return 0

        if status is None:
            return self.df.height

        status_values = [s.value for s in status]
        return self.df.filter(pl.col("result").is_in(status_values)).height

    def sort(self, sort_by: list[str]) -> ResultManager:
        """Get a sorted ResultManager based on specified fields."""
        self.ensure_dataframe_is_ready()

        accepted_fields = TestResult.model_fields.keys()
        if not set(sort_by).issubset(set(accepted_fields)):
            msg = f"Invalid sort_by fields: {sort_by}. Accepted fields are: {list(accepted_fields)}"
            raise ValueError(msg)

        if self.df.height == 0:
            return self.__class__()

        df_final = self.df

        # Polars sorting expression to replicate Python's 'or ""' or 'or []' null handling
        # It handles List<String> (like categories) by filling nulls with an empty list,
        # and standard types by filling nulls with an empty string.
        sort_expressions = [
            pl.col(field).fill_null(pl.lit([]).cast(pl.List(pl.Utf8))) if field == "categories" else pl.col(field).fill_null(pl.lit("")) for field in sort_by
        ]
        sorted_df = df_final.sort(sort_expressions)

        return ResultManager._from_df(df=sorted_df, status=self.status, error_status=self.error_status)

    def filter(self, hide: set[AntaTestStatus]) -> ResultManager:
        """Get a filtered ResultManager based on test status.

        Parameters
        ----------
        hide
            Set of AntaTestStatus enum members to select tests to hide based on their status.

        Returns
        -------
        ResultManager
            A filtered `ResultManager`.
        """
        self.ensure_dataframe_is_ready()
        if self.df.height == 0:
            return ResultManager()

        all_statuses = set(AntaTestStatus)
        statuses_to_keep = all_statuses - hide

        if not statuses_to_keep:
            return ResultManager()

        status_values_to_keep = [s.value for s in statuses_to_keep]
        filtered_df = self.df.filter(pl.col("result").is_in(status_values_to_keep))

        if filtered_df.height == 0:
            return ResultManager()

        # Calculate new status based on the filtered pl.DataFrame
        new_status, new_error_status = self._calculate_df_status(filtered_df)

        # Create the new manager instance directly from the pl.DataFrame
        return ResultManager._from_df(df=filtered_df, status=new_status, error_status=new_error_status)

    @classmethod
    def merge_results(cls, results_managers: list[ResultManager]) -> ResultManager:
        """Merge multiple ResultManager instances.

        Parameters
        ----------
        results_managers
            A list of ResultManager instances to merge.

        Returns
        -------
        ResultManager
            A new ResultManager instance containing the results of all the input ResultManagers.
        """
        status_order = {AntaTestStatus.ERROR: 5, AntaTestStatus.FAILURE: 4, AntaTestStatus.SKIPPED: 3, AntaTestStatus.SUCCESS: 2, AntaTestStatus.UNSET: 1}
        reverse_status_order = {v: k for k, v in status_order.items()}

        # Ensure all managers have processed their buffers and get non-empty pl.DataFrames
        non_empty_dfs: list[pl.DataFrame] = []
        max_severity_level = 0
        merged_error_status = False

        for rm in results_managers:
            rm.ensure_dataframe_is_ready()
            if rm.df.height > 0:
                non_empty_dfs.append(rm.df)

            # 2. Track highest status and error flag
            max_severity_level = max(max_severity_level, status_order.get(rm.status, 0))
            if rm.error_status:
                merged_error_status = True

        if not non_empty_dfs:
            return cls()

        merged_df = pl.concat(non_empty_dfs)
        merged_status = reverse_status_order.get(max_severity_level, AntaTestStatus.UNSET)

        return cls._from_df(df=merged_df, status=merged_status, error_status=merged_error_status)

    # ======================================================================
    # INTERNAL HELPERS (Polars Logic and State Management)
    # ======================================================================

    def _update_status(self, test_status: AntaTestStatus) -> None:
        """Update the status of the ResultManager instance based on the test status.

        Parameters
        ----------
        test_status
            AntaTestStatus to update the ResultManager status.
        """
        if test_status == "error":
            self.error_status = True
            return
        if self.status == "unset" or (self.status == "skipped" and test_status in {"success", "failure"}):
            self.status = test_status
        elif self.status == "success" and test_status == "failure":
            self.status = AntaTestStatus.FAILURE

    def ensure_dataframe_is_ready(self) -> None:
        """Convert the results buffer into the final Polars pl.DataFrame if the buffer is not empty.

        This is called implicitly by analysis methods.
        """
        if self._results:
            logger.debug("Implicitly finalizing %s results into pl.DataFrame...", len(self._results))
            results_dicts = [r.model_dump() for r in self._results]
            new_df = pl.DataFrame(results_dicts)
            if self.df.height == 0:
                self.df = new_df
            else:
                self.df = pl.concat([self.df, new_df])

            # Empty the buffer
            self._results.clear()

    def _calculate_df_status(self, df: pl.DataFrame) -> tuple[AntaTestStatus, bool]:
        """Calculate the combined AntaTestStatus and error_status for a given pl.DataFrame."""
        if df.height == 0:
            return AntaTestStatus.UNSET, False

        new_error_status = df.filter(pl.col("result") == AntaTestStatus.ERROR.value).height > 0
        new_failure_present = df.filter(pl.col("result") == AntaTestStatus.FAILURE.value).height > 0
        new_success_present = df.filter(pl.col("result") == AntaTestStatus.SUCCESS.value).height > 0

        if new_error_status:
            new_status = AntaTestStatus.ERROR
        elif new_failure_present:
            new_status = AntaTestStatus.FAILURE
        elif new_success_present:
            new_status = AntaTestStatus.SUCCESS
        elif df.filter(pl.col("result") == AntaTestStatus.SKIPPED.value).height > 0:
            new_status = AntaTestStatus.SKIPPED
        else:
            new_status = AntaTestStatus.UNSET

        return new_status, new_error_status

    def _calculate_stats_by_column(self, group_col: Literal["name", "test", "categories"]) -> list[dict[str, Any]]:
        """Calculate status counts, category lists, and failed test lists grouped by a column using a single vectorized Polars operation."""
        self.ensure_dataframe_is_ready()
        if self.df.height == 0:
            return []

        df_to_group = self.df

        # Define the base expressions for status counts (e.g., tests_SUCCESS_count)
        # These counts will represent device counts if grouped by test,
        # or test counts if grouped by (device) name/categories.
        agg_expressions = [(pl.col("result") == status).sum().alias(f"tests_{status}_count") for status in _STATUS_VALUES]

        failure_statuses = [AntaTestStatus.FAILURE, AntaTestStatus.ERROR]

        if group_col == "name":
            # Aggregations needed for DeviceStats
            agg_expressions.extend(
                [
                    pl.col("categories").filter(pl.col("result").eq(AntaTestStatus.SKIPPED)).explode().unique().implode().alias("categories_skipped"),
                    pl.col("categories").filter(pl.col("result").is_in(failure_statuses)).explode().unique().implode().alias("categories_failed"),
                    pl.col("test").filter(pl.col("result").is_in(failure_statuses)).unique().alias("tests_failure"),
                ]
            )

        if group_col == "test":
            agg_expressions.append(pl.col("name").filter(pl.col("result").is_in(failure_statuses)).unique().alias("devices_failure"))

        elif group_col == "categories":
            # If grouping by categories, we must explode first, then group by the exploded column.
            df_to_group = self.df.explode("categories").rename({"categories": group_col})

        stats_df = df_to_group.group_by(group_col).agg(agg_expressions)

        return stats_df.to_dicts()

    def _map_stats_to_dataclass(
        self, group_col: Literal["name", "test", "categories"], target_class: type[DeviceStats | CategoryStats | TestStats]
    ) -> dict[str, Any]:
        """Calculate stats, iterate over results, and map them to the target dataclass.

        Handles the merging of counts and the category sets/failed test sets.
        """
        stats_list = self._calculate_stats_by_column(group_col)
        result_dict = {}

        # Determine the required field prefix for the output
        output_prefix = "devices_" if target_class is TestStats else "tests_"

        for d in stats_list:
            # Get the key and pop it from the dict
            key = d.pop(group_col)
            kwargs = {}

            # 1. Map Status Counts
            for status in _STATUS_VALUES:
                input_key = f"tests_{status}_count"
                output_key = f"{output_prefix}{status.lower()}_count"

                # Assign value from the Polars output key to the required dataclass input key
                kwargs[output_key] = d.get(input_key, 0)

            # 2. Map Sets
            if target_class is DeviceStats and group_col == "name":
                # These fields were aggregated in _calculate_stats_by_column when grouping by 'device'
                kwargs["categories_failed"] = set(d.get("categories_failed", []))
                kwargs["categories_skipped"] = set(d.get("categories_skipped", []))
                kwargs["tests_failure"] = set(d.get("tests_failure", []))

            elif target_class is TestStats and group_col == "test":
                # This field was aggregated in _calculate_stats_by_column when grouping by 'test_name'
                kwargs["devices_failure"] = set(d.get("devices_failure", []))

            # 3. Instantiate the dataclass.
            try:
                result_dict[key] = target_class(**kwargs)
            except TypeError as e:
                logger.error("Error instantiating %s for key '%s': %s", target_class.__name__, key, e)
                logger.debug("Kwargs used: %s", kwargs)
                raise

        return dict(sorted(result_dict.items()))

    # ----------------------------------------------------------------------
    # Deprecated land - cross the boundary at your own risk
    # ----------------------------------------------------------------------
    @deprecated("This method is deprecated. This will be removed in ANTA v2.0.0.", category=DeprecationWarning)
    def filter_by_tests(self, tests: set[str]) -> ResultManager:
        """Get a filtered ResultManager that only contains specific tests."""
        self.ensure_dataframe_is_ready()
        if self.df.height == 0 or not tests:
            return ResultManager()

        filtered_df = self.df.filter(pl.col("test").is_in(list(tests)))
        if filtered_df.height == 0:
            return ResultManager()

        new_status, new_error_status = self._calculate_df_status(filtered_df)
        return ResultManager._from_df(df=filtered_df, status=new_status, error_status=new_error_status)

    @deprecated("This method is deprecated. This will be removed in ANTA v2.0.0.", category=DeprecationWarning)
    def filter_by_devices(self, devices: set[str]) -> ResultManager:
        """Get a filtered ResultManager that only contains specific devices."""
        self.ensure_dataframe_is_ready()
        if self.df.height == 0 or not devices:
            return ResultManager()

        filtered_df = self.df.filter(pl.col("name").is_in(list(devices)))
        if filtered_df.height == 0:
            return ResultManager()

        new_status, new_error_status = self._calculate_df_status(filtered_df)
        return ResultManager._from_df(df=filtered_df, status=new_status, error_status=new_error_status)

    @deprecated("This method is deprecated. This will be removed in ANTA v2.0.0.", category=DeprecationWarning)
    def get_tests(self) -> set[str]:
        """Get the set of all the test names."""
        self.ensure_dataframe_is_ready()
        if self.df.height == 0:
            return set()

        return set(self.df.select("test").unique().to_series().to_list())

    @deprecated("This method is deprecated. This will be removed in ANTA v2.0.0.", category=DeprecationWarning)
    def get_devices(self) -> set[str]:
        """Get the set of all the device names."""
        self.ensure_dataframe_is_ready()

        if self.df.height == 0:
            return set()

        return set(self.df.select("name").unique().to_series().to_list())
