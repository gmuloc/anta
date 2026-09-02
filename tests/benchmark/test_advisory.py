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
    CommandFactDefinition,
    Fact,
    FactDefinition,
    FactSource,
    FactSourceKind,
    MultiCommandFactDefinition,
)
from anta._advisory.optional_commands import OptionalAntaCommand
from anta._eos.version import parse_eos_version
from anta.device import AntaDevice
from anta.models import AntaCommand
from anta.result_manager.models import AntaTestStatus
from anta.tests.advisories.sa_117 import VerifySA117
from anta.tests.advisories.sa_142 import VerifySA142
from anta.tests.advisories.sa_146 import ADVISORY as SA146_ADVISORY
from anta.tests.advisories.sa_146 import VerifySA146
from anta.tests.advisories.sa_147 import VerifySA147
from tests.units.anta_tests.advisories.test_sa_117 import sa117_eos_data
from tests.units.anta_tests.advisories.test_sa_142 import pbr_output, sa142_eos_data
from tests.units.anta_tests.advisories.test_sa_146 import gnmi_output, sa146_eos_data
from tests.units.anta_tests.advisories.test_sa_147 import sa147_eos_data
from tests.units.anta_tests.advisories.test_sa_147 import version_output as sa147_version_output

if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture

    from anta.device import DevicePlatform, DeviceVersion

logger = logging.getLogger(__name__)

FACT_COUNTS = (1, 8, 32, 128)
ALL_FACT_ROUNDS = 10
LAST_FACT_LOOKUPS = 100
COLLECTION_COUNTS = (1, 2, 5, 20)
UNSUPPORTED_ERROR = "This command is not supported on this hardware platform"

CollectionOutcome = Literal["success", "failure", "unsupported"]
CommandTopology = Literal["shared", "unique"]
CacheMode = Literal["enabled", "disabled", "mixed"]
WrapperMode = Literal["required", "mixed"]
FactLookupMode = Literal["all", "last"]
FactShape = Literal["metadata", "command", "multi-command"]
FACT_SHAPES: tuple[FactShape, ...] = ("metadata", "command", "multi-command")


class _BenchmarkDevice(AntaDevice):
    """Deterministic device recording physical collection calls."""

    def __init__(self, *, disable_cache: bool, outcome: CollectionOutcome = "success") -> None:
        super().__init__("advisory-benchmark", disable_cache=disable_cache)
        self.outcome = outcome
        self.collect_calls = 0

    @property
    def _keys(self) -> tuple[str]:
        """Return the stable device identity."""
        return (self.name,)

    async def _collect(self, command: AntaCommand, *, collection_id: str | None = None) -> None:
        """Populate a deterministic output or error and count the device call."""
        _ = collection_id
        self.collect_calls += 1
        if self.outcome == "success":
            command.output = {"value": self.collect_calls}
            command.errors = []
        else:
            command.output = None
            command.errors = [UNSUPPORTED_ERROR if self.outcome == "unsupported" else "Synthetic collection failure"]

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


class _SyntheticCommandFactDefinition(CommandFactDefinition[int]):
    """Single-command fact used to include positional command binding cost."""

    key = "benchmark.synthetic.command.base"
    label = "Synthetic command benchmark fact"
    command = AntaCommand(command="show synthetic command base", revision=1)
    value: ClassVar[int] = 0

    @classmethod
    def parse(cls, command: AntaCommand) -> Fact[int]:
        """Return the value declared by the concrete synthetic definition."""
        return cls.available(cls.value, FactSource(command.command, FactSourceKind.COMMAND))


class _SyntheticMultiCommandFactDefinition(MultiCommandFactDefinition[int]):
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
        attributes["command"] = AntaCommand(command=f"show synthetic command {index}", revision=1)
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


@pytest.mark.parametrize(("shape", "fact_count"), FACT_CASES)
@pytest.mark.parametrize("lookup_mode", ["all", "last"])
def test_fact_lookup(benchmark: BenchmarkFixture, shape: FactShape, fact_count: int, lookup_mode: FactLookupMode) -> None:
    """Benchmark fact derivation as the required-fact declaration grows."""
    test_type = SYNTHETIC_TEST_TYPES[(shape, fact_count)]
    test_instance = test_type(device=_BenchmarkDevice(disable_cache=True), eos_data=[{} for _ in test_type.commands])
    facts = test_type.required_facts

    if lookup_mode == "all":

        @benchmark
        def result() -> int:
            checksum = 0
            for _ in range(ALL_FACT_ROUNDS):
                for definition in facts:
                    fact = cast("AvailableFact[int]", test_instance.fact(definition))
                    checksum += fact.value
            return checksum

    else:
        definition = facts[-1]

        @benchmark
        def result() -> int:
            checksum = 0
            for _ in range(LAST_FACT_LOOKUPS):
                fact = cast("AvailableFact[int]", test_instance.fact(definition))
                checksum += fact.value
            return checksum

    assert isinstance(result, int)


@dataclass(frozen=True, slots=True)
class _CollectionCase:
    """One command-collection benchmark scenario."""

    name: str
    count: int
    disable_device_cache: bool
    outcome: CollectionOutcome = "success"
    topology: CommandTopology = "shared"
    cache_mode: CacheMode = "enabled"
    wrapper_mode: WrapperMode = "required"

    @property
    def expected_collect_calls(self) -> int:
        """Return the physical calls made by the current collection contract."""
        if self.outcome != "success" or self.disable_device_cache or self.cache_mode == "disabled" or self.topology == "unique":
            return self.count
        if self.cache_mode == "mixed":
            uncached = self.count // 2
            cached = self.count - uncached
            return uncached + int(cached > 0)
        return 1


def _collection_case(
    name: str,
    count: int,
    *,
    disable_device_cache: bool = False,
    outcome: CollectionOutcome = "success",
    topology: CommandTopology = "shared",
    cache_mode: CacheMode = "enabled",
    wrapper_mode: WrapperMode = "required",
) -> object:
    """Build one named collection parameter."""
    return pytest.param(
        _CollectionCase(name, count, disable_device_cache, outcome, topology, cache_mode, wrapper_mode),
        id=f"{name}-{count}-commands",
    )


COLLECTION_CASES = (
    *(_collection_case("cached-shared-success", count) for count in COLLECTION_COUNTS),
    *(_collection_case("device-cache-disabled", count, disable_device_cache=True) for count in COLLECTION_COUNTS),
    *(_collection_case("cached-shared-failure", count, outcome="failure") for count in COLLECTION_COUNTS),
    _collection_case("cached-shared-unsupported", 20, outcome="unsupported", wrapper_mode="mixed"),
    _collection_case("command-cache-disabled", 20, cache_mode="disabled"),
    _collection_case("mixed-command-cache", 20, cache_mode="mixed"),
    _collection_case("mixed-wrapper", 20, wrapper_mode="mixed"),
    _collection_case("unique-commands", 20, topology="unique"),
)


def _build_commands(case: _CollectionCase) -> list[AntaCommand]:
    """Build exact command instances for a collection scenario."""
    commands: list[AntaCommand] = []
    for index in range(case.count):
        command_text = f"show benchmark {index}" if case.topology == "unique" else "show benchmark"
        use_cache = case.cache_mode == "enabled" or (case.cache_mode == "mixed" and index % 2 == 0)
        command_type = OptionalAntaCommand if case.wrapper_mode == "mixed" and index % 2 == 0 else AntaCommand
        commands.append(command_type(command=command_text, revision=1, use_cache=use_cache))
    return commands


@pytest.mark.parametrize("case", COLLECTION_CASES)
def test_command_collection(benchmark: BenchmarkFixture, case: _CollectionCase) -> None:
    """Benchmark physical collection under cache, UID, wrapper, and failure variants."""
    device = _BenchmarkDevice(disable_cache=case.disable_device_cache, outcome=case.outcome)
    loop = asyncio.new_event_loop()
    last_commands: list[AntaCommand] = []

    def run() -> int:
        nonlocal last_commands
        device.collect_calls = 0
        if device.cache is not None:
            device.cache.clear()
        last_commands = _build_commands(case)
        loop.run_until_complete(device.collect_commands(last_commands, collection_id=case.name))
        return device.collect_calls

    logging.disable()
    try:
        collect_calls = benchmark(run)
    finally:
        logging.disable(logging.NOTSET)
        loop.close()

    assert collect_calls == case.expected_collect_calls
    if case.outcome == "success":
        assert all(command.output is not None and not command.errors for command in last_commands)
    else:
        assert all(command.output is None and command.errors for command in last_commands)
    if case.wrapper_mode == "mixed":
        assert all(isinstance(command, OptionalAntaCommand) is (index % 2 == 0) for index, command in enumerate(last_commands))

    logger.info(
        "Advisory collection benchmark %s: command objects=%d, unique UIDs=%d, physical calls=%d",
        case.name,
        len(last_commands),
        len({command.uid for command in last_commands}),
        collect_calls,
    )


@dataclass(frozen=True, slots=True)
class _AdvisoryCase:
    """Representative end-to-end advisory execution."""

    name: str
    test_type: type[_AntaAdvisoryTest]
    version: str
    eos_data: tuple[dict[str, Any] | str, ...]
    expected_status: AntaTestStatus
    platform: DevicePlatform | None = None


SA142_AFFECTED_DATA = sa142_eos_data(pbr=pbr_output())


ADVISORY_CASES = (
    pytest.param(
        _AdvisoryCase(
            "sa117-inconclusive",
            cast("type[_AntaAdvisoryTest]", VerifySA117),
            "4.32.4M",
            tuple(sa117_eos_data({"transports": {"default": {"enabled": True, "accounting": True}}}, "")),
            AntaTestStatus.INCONCLUSIVE,
        ),
        id="sa117-inconclusive",
    ),
    pytest.param(
        _AdvisoryCase(
            "sa142-affected",
            cast("type[_AntaAdvisoryTest]", VerifySA142),
            "4.35.4M",
            tuple(SA142_AFFECTED_DATA["eos_data"]),
            AntaTestStatus.FAILURE,
            platform=SA142_AFFECTED_DATA["platform"],
        ),
        id="sa142-affected",
    ),
    pytest.param(
        _AdvisoryCase(
            "sa146-affected",
            cast("type[_AntaAdvisoryTest]", VerifySA146),
            "4.35.5M",
            tuple(sa146_eos_data(gnmi=gnmi_output(enabled=True))),
            AntaTestStatus.FAILURE,
        ),
        id="sa146-affected",
    ),
    pytest.param(
        _AdvisoryCase(
            "sa147-affected",
            cast("type[_AntaAdvisoryTest]", VerifySA147),
            "4.35.5M",
            tuple(sa147_eos_data(sa147_version_output(), "")),
            AntaTestStatus.FAILURE,
        ),
        id="sa147-affected",
    ),
)


@pytest.mark.parametrize("case", ADVISORY_CASES)
def test_advisory_end_to_end(benchmark: BenchmarkFixture, case: _AdvisoryCase) -> None:
    """Benchmark test initialization, fact derivation, assessment, and projection."""
    device = _BenchmarkDevice(disable_cache=True)
    device.version = cast("DeviceVersion", parse_eos_version(case.version))
    device.platform = case.platform
    loop = asyncio.new_event_loop()

    async def run() -> AntaTestStatus:
        test_instance = case.test_type(device=device)
        result = await cast("Any", test_instance).test(eos_data=list(case.eos_data))
        return result.result

    logging.disable()
    try:
        status = benchmark(lambda: loop.run_until_complete(run()))
    finally:
        logging.disable(logging.NOTSET)
        loop.close()

    assert status is case.expected_status
