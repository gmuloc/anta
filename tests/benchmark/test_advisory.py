# Copyright (c) 2026 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
"""Benchmark structured security-advisory execution."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

import pytest

from anta._advisory.base import _AntaAdvisoryTest
from anta._advisory.facts.models import (
    AvailableFact,
    CommandsFactDefinition,
    Fact,
    FactDefinition,
    FactSource,
    FactSourceKind,
)
from anta._advisory.status import AdvisoryStatus
from anta._eos.version import parse_eos_version
from anta.device import AntaDevice
from anta.models import AntaCommand
from anta.result_manager.models import AntaTestStatus
from anta.tests.advisories.sa_117 import SA117
from anta.tests.advisories.sa_142 import SA142
from anta.tests.advisories.sa_146 import ADVISORY as SA146_ADVISORY
from anta.tests.advisories.sa_146 import SA146
from anta.tests.advisories.sa_147 import SA147
from tests.units.anta_tests.advisories.test_sa_117 import sa117_eos_data
from tests.units.anta_tests.advisories.test_sa_142 import pbr_output, sa142_eos_data
from tests.units.anta_tests.advisories.test_sa_146 import gnmi_output, sa146_eos_data
from tests.units.anta_tests.advisories.test_sa_147 import sa147_eos_data
from tests.units.anta_tests.advisories.test_sa_147 import version_output as sa147_version_output

if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture

    from anta.device import DevicePlatform

FACT_COUNTS = (1, 8, 32, 128)
FactShape = Literal["metadata", "command", "multi-command"]
FACT_SHAPES: tuple[FactShape, ...] = ("metadata", "command", "multi-command")


class _BenchmarkDevice(AntaDevice):
    """Minimal deterministic device used by advisory benchmarks."""

    def __init__(self) -> None:
        super().__init__("advisory-benchmark", disable_cache=True)

    @property
    def _keys(self) -> tuple[str]:
        """Return the stable device identity."""
        return (self.name,)

    async def _collect(self, command: AntaCommand, *, collection_id: str | None = None) -> None:
        """Populate deterministic output when a benchmark performs collection."""
        _ = collection_id
        command.output = {}
        command.errors = []

    async def refresh(self) -> None:
        """Mark the benchmark device available."""
        self.is_online = True
        self.established = True


SYNTHETIC_SOURCE = FactSource("benchmark metadata", FactSourceKind.DEVICE_METADATA)


class _SyntheticFactDefinition(FactDefinition[int]):
    """Metadata-only fact used to scale positional lookup."""

    key = "benchmark.synthetic.base"
    label = "Synthetic benchmark fact"
    value: ClassVar[int] = 0

    @classmethod
    def derive(cls, device: AntaDevice, commands: tuple[AntaCommand, ...] = ()) -> Fact[int]:
        """Return the value declared by the concrete synthetic definition."""
        _ = device, commands
        return cls.available(cls.value, SYNTHETIC_SOURCE)


class _SyntheticCommandFactDefinition(CommandsFactDefinition[int]):
    """Single-command fact used to include positional command binding cost."""

    key = "benchmark.synthetic.command.base"
    label = "Synthetic command benchmark fact"
    commands = (AntaCommand(command="show synthetic command base", revision=1),)
    value: ClassVar[int] = 0

    @classmethod
    def parse(cls, commands: tuple[AntaCommand, ...]) -> Fact[int]:
        """Return the value declared by the concrete synthetic definition."""
        return cls.available(cls.value, FactSource(commands[0].command, FactSourceKind.COMMAND))


class _SyntheticMultiCommandFactDefinition(CommandsFactDefinition[int]):
    """Two-command fact used to include positional command-slice cost."""

    key = "benchmark.synthetic.multi.base"
    label = "Synthetic multi-command benchmark fact"
    commands = (
        AntaCommand(command="show synthetic multi base first", revision=1),
        AntaCommand(command="show synthetic multi base second", revision=1),
    )
    value: ClassVar[int] = 0

    @classmethod
    def parse(cls, commands: tuple[AntaCommand, ...]) -> Fact[int]:
        """Return the value declared by the concrete synthetic definition."""
        source = FactSource(" and ".join(command.command for command in commands), FactSourceKind.COMMAND)
        return cls.available(cls.value, source)


def _synthetic_fact(index: int, shape: FactShape) -> type[FactDefinition[int]]:
    """Create one distinctly keyed fact definition of the requested shape."""
    base: type[FactDefinition[int]]
    attributes: dict[str, object] = {
        "key": f"benchmark.synthetic.{shape}.{index}",
        "label": f"Synthetic {shape} benchmark fact {index}",
        "value": index,
    }
    if shape == "metadata":
        base = _SyntheticFactDefinition
    elif shape == "command":
        base = _SyntheticCommandFactDefinition
        attributes["commands"] = (AntaCommand(command=f"show synthetic command {index}", revision=1),)
    else:
        base = _SyntheticMultiCommandFactDefinition
        attributes["commands"] = (
            AntaCommand(command=f"show synthetic multi {index} first", revision=1),
            AntaCommand(command=f"show synthetic multi {index} second", revision=1),
        )
    fact_type = type(
        f"_Synthetic{shape.title().replace('-', '')}Fact{index}",
        (base,),
        attributes,
    )
    return cast("type[FactDefinition[int]]", fact_type)


SYNTHETIC_FACTS = {shape: tuple(_synthetic_fact(index, shape) for index in range(max(FACT_COUNTS))) for shape in FACT_SHAPES}


def _benchmark_test_type(fact_count: int, shape: FactShape) -> type[_AntaAdvisoryTest]:
    """Create an advisory test with the requested fact count and shape."""

    def test(self: _AntaAdvisoryTest) -> None:
        """Set a terminal result when the generated test body is executed."""
        self.result.is_success()

    test_type = type(
        f"_Synthetic{shape.title().replace('-', '')}Advisory{fact_count}",
        (_AntaAdvisoryTest,),
        {
            "__doc__": f"Synthetic advisory with {fact_count} facts.",
            "advisory": SA146_ADVISORY,
            "required_facts": SYNTHETIC_FACTS[shape][:fact_count],
            "test": _AntaAdvisoryTest.anta_test(test),
        },
    )
    return cast("type[_AntaAdvisoryTest]", test_type)


FACT_TEST_KEYS: tuple[tuple[FactShape, int], ...] = tuple(
    (shape, fact_count) for shape in FACT_SHAPES for fact_count in (FACT_COUNTS if shape == "metadata" else (8, 128))
)
FACT_CASES = [pytest.param(shape, fact_count, id=f"{shape}-{fact_count}-facts") for shape, fact_count in FACT_TEST_KEYS]
SYNTHETIC_TEST_TYPES = {(shape, fact_count): _benchmark_test_type(fact_count, shape) for shape, fact_count in FACT_TEST_KEYS}


# Preserve this test name, its parameter IDs, and the derive-all workload when
# adapting the benchmark to typed Facts containers so CodSpeed can compare runs.
@pytest.mark.parametrize(("shape", "fact_count"), FACT_CASES)
def test_fact_lookup(benchmark: BenchmarkFixture, shape: FactShape, fact_count: int) -> None:
    """Benchmark deriving every fact required by one advisory execution."""
    test_type = SYNTHETIC_TEST_TYPES[(shape, fact_count)]
    test_instance = test_type(device=_BenchmarkDevice(), eos_data=[{} for _ in test_type.commands])

    def run() -> int:
        facts = tuple(cast("AvailableFact[int]", test_instance.fact(definition)) for definition in test_type.required_facts)
        return sum(fact.value for fact in facts)

    result = benchmark(run)
    assert result == sum(range(fact_count))


@dataclass(frozen=True, slots=True)
class _AdvisoryCase:
    """Representative end-to-end advisory execution."""

    name: str
    test_type: type[_AntaAdvisoryTest]
    version: str
    eos_data: tuple[dict[str, Any] | str, ...]
    expected_result: AntaTestStatus
    expected_advisory_status: AdvisoryStatus
    platform: DevicePlatform | None = None


SA142_AFFECTED_DATA = sa142_eos_data(pbr=pbr_output())


ADVISORY_CASES = (
    pytest.param(
        _AdvisoryCase(
            "sa117-inconclusive",
            cast("type[_AntaAdvisoryTest]", SA117),
            "4.32.4M",
            tuple(sa117_eos_data({"transports": {"default": {"enabled": True, "accounting": True}}}, "")),
            AntaTestStatus.FAILURE,
            AdvisoryStatus.INCONCLUSIVE,
        ),
        id="sa117-inconclusive",
    ),
    pytest.param(
        _AdvisoryCase(
            "sa142-affected",
            cast("type[_AntaAdvisoryTest]", SA142),
            "4.35.4M",
            tuple(SA142_AFFECTED_DATA["eos_data"]),
            AntaTestStatus.FAILURE,
            AdvisoryStatus.AFFECTED,
            platform=SA142_AFFECTED_DATA["platform"],
        ),
        id="sa142-affected",
    ),
    pytest.param(
        _AdvisoryCase(
            "sa146-affected",
            cast("type[_AntaAdvisoryTest]", SA146),
            "4.35.5M",
            tuple(sa146_eos_data(gnmi=gnmi_output(enabled=True))),
            AntaTestStatus.FAILURE,
            AdvisoryStatus.AFFECTED,
        ),
        id="sa146-affected",
    ),
    pytest.param(
        _AdvisoryCase(
            "sa147-affected",
            cast("type[_AntaAdvisoryTest]", SA147),
            "4.35.5M",
            tuple(sa147_eos_data(sa147_version_output(), "")),
            AntaTestStatus.FAILURE,
            AdvisoryStatus.AFFECTED,
        ),
        id="sa147-affected",
    ),
)


@pytest.mark.parametrize("case", ADVISORY_CASES)
def test_advisory_end_to_end(benchmark: BenchmarkFixture, case: _AdvisoryCase) -> None:
    """Benchmark test initialization, fact derivation, assessment, and projection."""
    device = _BenchmarkDevice()
    device.version = parse_eos_version(case.version).unwrap()
    device.platform = case.platform
    loop = asyncio.new_event_loop()

    async def run() -> tuple[AntaTestStatus, AdvisoryStatus | None]:
        test_instance = case.test_type(device=device)
        result = await cast("Any", test_instance).test(eos_data=list(case.eos_data))
        return result.result, result.advisory_status

    logging.disable()
    try:
        result, advisory_status = benchmark(lambda: loop.run_until_complete(run()))
    finally:
        logging.disable(logging.NOTSET)
        loop.close()

    assert result is case.expected_result
    assert advisory_status is case.expected_advisory_status
