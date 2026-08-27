# Copyright (c) 2026 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""Unit tests for EOS version parsing helpers."""

from __future__ import annotations

import pytest

from anta._eos.version import EOSVersion, parse_eos_version


@pytest.mark.parametrize(
    ("version_string", "expected"),
    [
        pytest.param(" 4.36.1FX-build ", EOSVersion(major=4, minor=36, patch=1, suffix="FX-build"), id="suffix"),
        pytest.param("4.34.7.1M", EOSVersion(major=4, minor=34, patch=7, hotfix=1, suffix="M"), id="hotfix"),
        pytest.param(
            "4.31.1F-34361447.fraserrel (engineering build)",
            EOSVersion(major=4, minor=31, patch=1, suffix="F-34361447.fraserrel (engineering build)"),
            id="engineering-build",
        ),
        pytest.param("4.33.1", EOSVersion(major=4, minor=33, patch=1), id="no-suffix"),
        pytest.param("unknown", None, id="invalid"),
        pytest.param("4.33", None, id="incomplete"),
    ],
)
def test_parse_eos_version(version_string: str, expected: EOSVersion | None) -> None:
    """Verify EOS version parsing."""
    version = parse_eos_version(version_string)

    assert version == expected
    if version is not None:
        assert version.raw == version_string.strip()


def test_numeric_key() -> None:
    """Verify numeric keys normalize a missing hotfix to zero."""
    assert EOSVersion(major=4, minor=34, patch=7).numeric_key == (4, 34, 7, 0)
    assert EOSVersion(major=4, minor=34, patch=7, hotfix=1).numeric_key == (4, 34, 7, 1)


def test_parse_raises_for_invalid_version() -> None:
    """Verify strict parsing reports invalid values."""
    with pytest.raises(ValueError, match="Invalid EOS version string"):
        EOSVersion.parse("4.33")
