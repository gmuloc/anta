# Copyright (c) 2026 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""Arista EOS version parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

EOS_VERSION_PATTERN = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:\.(?P<hotfix>\d+))?(?P<suffix>.*)$"
)


@dataclass(frozen=True, slots=True)
class EOSVersion:
    """Normalized representation of an EOS release string."""

    major: int
    minor: int
    patch: int
    hotfix: int | None = None
    suffix: str = ""
    raw: str = field(default="", compare=False, repr=False)

    @property
    def numeric_key(self) -> tuple[int, int, int, int]:
        """Return the numeric components suitable for release-range comparisons."""
        return (self.major, self.minor, self.patch, self.hotfix or 0)

    @classmethod
    def parse(cls, version_string: str) -> EOSVersion:
        """Parse an EOS version string.

        Raises
        ------
        ValueError
            If the value does not contain a complete EOS numeric version.

        """
        raw = version_string.strip()
        match = EOS_VERSION_PATTERN.fullmatch(raw)
        if match is None:
            msg = f"Invalid EOS version string: {version_string!r}"
            raise ValueError(msg)

        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            hotfix=int(hotfix) if (hotfix := match.group("hotfix")) is not None else None,
            suffix=match.group("suffix").strip(),
            raw=raw,
        )

    @classmethod
    def try_parse(cls, version_string: str) -> EOSVersion | None:
        """Parse an EOS version string, returning `None` when it is invalid."""
        try:
            return cls.parse(version_string)
        except ValueError:
            return None


def parse_eos_version(version_string: str) -> EOSVersion | None:
    """Parse an EOS version string, returning `None` when it is invalid."""
    return EOSVersion.try_parse(version_string)
