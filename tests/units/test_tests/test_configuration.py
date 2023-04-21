# pylint: skip-file
"""
Tests for anta.tests.configuration.py
"""
import asyncio
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from httpx import HTTPError

from anta.tests.configuration import VerifyZeroTouch, verify_running_config_diffs


@pytest.mark.parametrize(
    "eos_data, side_effect, expected_result, expected_messages",
    [
        pytest.param([{"mode": "disabled"}], None, "success", [], id="success"),
        pytest.param(
            [{"mode": "enabled"}],
            None,
            "failure",
            ["ZTP is NOT disabled"],
            id="failure",
        ),
        # Hmmmm both errors do not return the same string ...
        # TODO: need to cover other exceptions like EapiCommandError
        pytest.param(
            None, HTTPError("dummy"), "error", ["HTTPError (dummy)"], id="HTTP error"
        ),
        pytest.param(
            None, KeyError("dummy"), "error", ["KeyError ('dummy')"], id="Key error"
        ),
    ],
)
def test_VerifyZeroTouch(
    mocked_device: MagicMock,
    eos_data: List[Dict[str, str]],
    side_effect: Any,
    expected_result: str,
    expected_messages: List[str],
) -> None:
    # TODO mock per command probably ..
    if eos_data:
        mocked_device.session.cli.return_value = eos_data[0]
    mocked_device.session.cli.side_effect = side_effect
    # TODO technically could avoid mocking to only test the assert part
    test = VerifyZeroTouch(mocked_device)
    asyncio.run(test.test())

    assert test.name == "verify_zerotouch"
    assert test.categories == ["configuration"]
    assert test.result.test == "verify_zerotouch"
    assert str(test.result.name) == mocked_device.name
    assert test.result.result == expected_result
    assert test.result.messages == expected_messages


@pytest.mark.parametrize(
    "return_value, side_effect, remove_enable_password, expected_result, expected_messages",
    [
        pytest.param(
            [None, []],
            None,
            False,
            "success",
            [],
            id="success",
        ),
        pytest.param(
            [None, "blah\nblah"],
            None,
            False,
            "failure",
            ["blah", "blah"],
            id="failure",
        ),
        # Hmmmm both errors do not return the same string ...
        pytest.param(
            None,
            HTTPError("dummy"),
            False,
            "error",
            ["HTTPError (dummy)"],
            id="HTTP error",
        ),
        pytest.param(
            None,
            KeyError("dummy"),
            False,
            "error",
            ["KeyError ('dummy')"],
            id="Key error",
        ),
        pytest.param(
            [None, []],
            None,
            False,
            "success",
            [],
            id="success",
        ),
    ],
)
def test_verify_running_config_diffs(
    mocked_device: MagicMock,
    return_value: List[Any],
    side_effect: Any,
    remove_enable_password: str,
    expected_result: str,
    expected_messages: List[str],
) -> None:
    if remove_enable_password:
        mocked_device.enable_password = None
    mocked_device.session.cli.return_value = return_value
    mocked_device.session.cli.side_effect = side_effect
    result = asyncio.run(verify_running_config_diffs(mocked_device))

    assert result.test == "verify_running_config_diffs"
    assert str(result.name) == mocked_device.name
    assert result.result == expected_result
    assert result.messages == expected_messages
