"""
BGP test functions
"""
import inspect
import socket
import logging

from typing import Dict, Any
from jsonrpclib import jsonrpc
from anta.decorators import check_bgp_family_enable
from anta.inventory.models import InventoryDevice
from anta.result_manager.models import TestResult

logger = logging.getLogger(__name__)


@check_bgp_family_enable("ipv4")
def verify_bgp_ipv4_unicast_state(device: InventoryDevice) -> TestResult:
    """
    Verifies all IPv4 unicast BGP sessions are established (for all VRF)
    and all BGP messages queues for these sessions are empty (for all VRF).

    Args:
        device (InventoryDevice): InventoryDevice instance containing all devices information.

    Returns:
        TestResult instance with
        * result = "unset" if the test has not been executed
        * result = "skipped" if no BGP vrf are returned by the device
        * result = "success" if all IPv4 unicast BGP sessions are established (for all VRF)
                             and all BGP messages queues for these sessions are empty (for all VRF).
        * result = "failure" otherwise.
        * result = "error" if any exception is caught
    """
    function_name = inspect.stack()[0][3]
    logger.debug(f"Start {function_name} check for host {device.host}")
    result = TestResult(host=str(device.host), test=function_name)

    try:
        response = device.session.runCmds(
            1, ["show bgp ipv4 unicast summary vrf all"], "json"
        )
        logger.debug(f"query result is: {response}")

        bgp_vrfs = response[0]["vrfs"]

        state_issue: Dict[str, Any] = {}
        for vrf in bgp_vrfs:
            for peer in bgp_vrfs[vrf]["peers"]:
                if (
                    (bgp_vrfs[vrf]["peers"][peer]["peerState"] != "Established")
                    or (bgp_vrfs[vrf]["peers"][peer]["inMsgQueue"] != 0)
                    or (bgp_vrfs[vrf]["peers"][peer]["outMsgQueue"] != 0)
                ):
                    vrf_dict = state_issue.setdefault(vrf, {})
                    vrf_dict.update(
                        {
                            peer: {
                                "peerState": bgp_vrfs[vrf]["peers"][peer]["peerState"],
                                "inMsgQueue": bgp_vrfs[vrf]["peers"][peer][
                                    "inMsgQueue"
                                ],
                                "outMsgQueue": bgp_vrfs[vrf]["peers"][peer][
                                    "outMsgQueue"
                                ],
                            }
                        }
                    )

        if not state_issue:
            result.is_success()
        else:
            result.is_failure(f"Some IPv4 Unicast BGP Peer are not up: {state_issue}")

    except (jsonrpc.AppError, KeyError, socket.timeout) as e:
        logger.error(
            f"exception raised for {inspect.stack()[0][3]} -  {device.host}: {str(e)}"
        )

        result.is_error(str(e))
    return result


@check_bgp_family_enable("ipv4")
def verify_bgp_ipv4_unicast_count(
    device: InventoryDevice, number: int, vrf: str = "default"
) -> TestResult:
    """
    Verifies all IPv4 unicast BGP sessions are established
    and all BGP messages queues for these sessions are empty
    and the actual number of BGP IPv4 unicast neighbors is the one we expect.

    Args:
        device (InventoryDevice): InventoryDevice instance containing all devices information.
        number (int): Expected number of BGP IPv4 unicast neighbors
        vrf(str): VRF to verify. default is "default".

    Returns:
        TestResult instance with
        * result = "unset" if the test has not been executed
        * result = "skipped" if the `number` or `vrf` parameter is missing
        * result = "success" if all IPv4 unicast BGP sessions are established
                             and if all BGP messages queues for these sessions are empty
                             and if the actual number of BGP IPv4 unicast neighbors is equal to `number.
        * result = "failure" otherwise.
        * result = "error" if any exception is caught
    """
    function_name = inspect.stack()[0][3]
    logger.debug(f"Start {function_name} check for host {device.host}")
    result = TestResult(host=str(device.host), test=function_name)

    if not number or not vrf:
        result.is_skipped(
            "verify_bgp_ipv4_unicast_count could not run because number of vrf was not supplied"
        )
        return result

    try:
        response = device.session.runCmds(
            1, [f"show bgp ipv4 unicast summary vrf {vrf}"], "json"
        )
        logger.debug(f"query result is: {response}")

        bgp_vrfs = response[0]["vrfs"]

        peer_number = len(bgp_vrfs[vrf]["peers"])

        peer_state_issue = {
            peer: {
                "peerState": bgp_vrfs[vrf]["peers"][peer]["peerState"],
                "inMsgQueue": bgp_vrfs[vrf]["peers"][peer]["inMsgQueue"],
                "outMsgQueue": bgp_vrfs[vrf]["peers"][peer]["outMsgQueue"],
            }
            for peer in bgp_vrfs[vrf]["peers"]
            if (
                (bgp_vrfs[vrf]["peers"][peer]["peerState"] != "Established")
                or (bgp_vrfs[vrf]["peers"][peer]["inMsgQueue"] != 0)
                or (bgp_vrfs[vrf]["peers"][peer]["outMsgQueue"] != 0)
            )
        }

        if peer_number == number or peer_state_issue:
            result.is_success()
        else:
            result.is_failure(
                f"Expecting {number} BGP peer in vrf {vrf} and got {peer_number}"
            )
            if peer_state_issue:
                result.is_failure(
                    f"Some IPv4 Unicast BGP Peer are not up: {peer_state_issue}"
                )

    except (jsonrpc.AppError, KeyError, socket.timeout) as e:
        logger.error(
            f"exception raised for {inspect.stack()[0][3]} -  {device.host}: {str(e)}"
        )
        result.is_error(str(e))
    return result


@check_bgp_family_enable("ipv6")
def verify_bgp_ipv6_unicast_state(device: InventoryDevice) -> TestResult:
    """
    Verifies all IPv6 unicast BGP sessions are established (for all VRF)
    and all BGP messages queues for these sessions are empty (for all VRF).

    Args:
        device (InventoryDevice): InventoryDevice instance containing all devices information.

    Returns:
        TestResult instance with
        * result = "unset" if the test has not been executed
        * result = "skipped" if no BGP vrf are returned by the device
        * result = "success" if all IPv6 unicast BGP sessions are established (for all VRF)
                             and all BGP messages queues for these sessions are empty (for all VRF).
        * result = "failure" otherwise.
        * result = "error" if any exception is caught
    """
    function_name = inspect.stack()[0][3]
    logger.debug(f"Start {function_name} check for host {device.host}")
    result = TestResult(host=str(device.host), test=function_name)

    try:
        response = device.session.runCmds(
            1, ["show bgp ipv6 unicast summary vrf all"], "json"
        )

        logger.debug(f"query result is: {response}")
        bgp_vrfs = response[0]["vrfs"]

        state_issue: Dict[str, Any] = {}
        for vrf in bgp_vrfs:
            for peer in bgp_vrfs[vrf]["peers"]:
                if (
                    (bgp_vrfs[vrf]["peers"][peer]["peerState"] != "Established")
                    or (bgp_vrfs[vrf]["peers"][peer]["inMsgQueue"] != 0)
                    or (bgp_vrfs[vrf]["peers"][peer]["outMsgQueue"] != 0)
                ):
                    vrf_dict = state_issue.setdefault(vrf, {})
                    vrf_dict.update(
                        {
                            peer: {
                                "peerState": bgp_vrfs[vrf]["peers"][peer]["peerState"],
                                "inMsgQueue": bgp_vrfs[vrf]["peers"][peer][
                                    "inMsgQueue"
                                ],
                                "outMsgQueue": bgp_vrfs[vrf]["peers"][peer][
                                    "outMsgQueue"
                                ],
                            }
                        }
                    )

        if not state_issue:
            result.is_success()
        else:
            result.is_failure(f"Some IPv6 Unicast BGP Peer are not up: {state_issue}")

    except (jsonrpc.AppError, KeyError, socket.timeout) as e:
        logger.error(f"exception raised for {inspect.stack()[0][3]} -  {device.host}: {str(e)}")

        result.is_error(str(e))
    return result


@check_bgp_family_enable("evpn")
def verify_bgp_evpn_state(device: InventoryDevice) -> TestResult:

    """
    Verifies all EVPN BGP sessions are established (default VRF).

    Args:
        device (InventoryDevice): InventoryDevice instance containing all devices information.

    Returns:
        TestResult instance with
        * result = "unset" if the test has not been executed
        * result = "skipped" if no BGP EVPN peers are returned by the device
        * result = "success" if all EVPN BGP sessions are established.
        * result = "failure" otherwise.
        * result = "error" if any exception is caught

    """
    function_name = inspect.stack()[0][3]
    logger.debug(f"Start {function_name} check for host {device.host}")
    result = TestResult(host=str(device.host), test=function_name)

    try:
        response = device.session.runCmds(1, ["show bgp evpn summary"], "json")
        logger.debug(f"query result is: {response}")

        bgp_vrfs = response[0]["vrfs"]

        peers = bgp_vrfs["default"]["peers"]
        non_established_peers = [
            peer
            for peer, peer_dict in peers.items()
            if peer_dict["peerState"] != "Established"
        ]

        if not non_established_peers:
            result.is_success()
        else:
            result.is_failure(
                f"The following EVPN peers are not established: {non_established_peers}"
            )

    except (jsonrpc.AppError, KeyError, socket.timeout) as e:
        logger.error(
            f"exception raised for {inspect.stack()[0][3]} -  {device.host}: {str(e)}"
        )
        result.is_error(str(e))
    return result


@check_bgp_family_enable("evpn")
def verify_bgp_evpn_count(device: InventoryDevice, number: int) -> TestResult:
    """
    Verifies all EVPN BGP sessions are established (default VRF)
    and the actual number of BGP EVPN neighbors is the one we expect (default VRF).

    Args:
        device (InventoryDevice): InventoryDevice instance containing all devices information.
        number (int): The expected number of BGP EVPN neighbors in the default VRF.

    Returns:
        TestResult instance with
        * result = "unset" if the test has not been executed
        * result = "skipped" if the `number` parameter is missing
        * result = "success" if all EVPN BGP sessions are Established and if the actual
                             number of BGP EVPN neighbors is the one we expect.
        * result = "failure" otherwise.
        * result = "error" if any exception is caught

    """
    function_name = inspect.stack()[0][3]
    logger.debug(f"Start {function_name} check for host {device.host}")
    result = TestResult(host=str(device.host), test=function_name)

    if not number:
        result.is_skipped(
            "verify_bgp_evpn_count could not run because number was not supplied."
        )
        return result

    try:
        response = device.session.runCmds(1, ["show bgp evpn summary"], "json")
        logger.debug(f"query result is: {response}")

        peers = response[0]["vrfs"]["default"]["peers"]

        if len(peers) == number:
            result.is_success()
        else:
            result.is_failure()
            if len(peers) != number:
                result.messages.append(
                    f"Expecting {number} BGP EVPN peers and got {len(peers)}"
                )

    except (jsonrpc.AppError, KeyError, socket.timeout) as e:
        logger.error(
            f"exception raised for {inspect.stack()[0][3]} -  {device.host}: {str(e)}"
        )

        result.is_error(str(e))
    return result


@check_bgp_family_enable("rtc")
def verify_bgp_rtc_state(device: InventoryDevice) -> TestResult:
    """
    Verifies all RTC BGP sessions are established (default VRF).

    Args:
        device (InventoryDevice): InventoryDevice instance containing all devices information.

    Returns:
        TestResult instance with
        * result = "unset" if the test has not been executed
        * result = "skipped" if no BGP RTC peers are returned by the device
        * result = "success" if all RTC BGP sessions are Established.
        * result = "failure" otherwise.
        * result = "error" if any exception is caught

    """
    function_name = inspect.stack()[0][3]
    logger.debug(f"Start {function_name} check for host {device.host}")
    result = TestResult(host=str(device.host), test=function_name)

    try:
        response = device.session.runCmds(1, ["show bgp rt-membership summary"], "json")
        logger.debug(f"query result is: {response}")

        peers = response[0]["vrfs"]["default"]["peers"]
        non_established_peers = [
            peer
            for peer, peer_dict in peers.items()
            if peer_dict["peerState"] != "Established"
        ]

        if not non_established_peers:
            result.is_success()
        else:
            result.is_failure(
                f"The following RTC peers are not established: {non_established_peers}"
            )

    except (jsonrpc.AppError, KeyError, socket.timeout) as e:
        logger.error(
            f"exception raised for {inspect.stack()[0][3]} -  {device.host}: {str(e)}"
        )
        result.is_error(str(e))
    return result


@check_bgp_family_enable("rtc")
def verify_bgp_rtc_count(device: InventoryDevice, number: int) -> TestResult:
    """
    Verifies all RTC BGP sessions are established (default VRF)
    and the actual number of BGP RTC neighbors is the one we expect (default VRF).

    Args:
        device (InventoryDevice): InventoryDevice instance containing all devices information.
        number (int): The expected number of BGP RTC neighbors (default VRF).

    Returns:
        TestResult instance with
        * result = "unset" if the test has not been executed
        * result = "skipped" if the `number` parameter is missing
        * result = "success" if all RTC BGP sessions are established
                             and if the actual number of BGP RTC neighbors is the one we expect.
        * result = "failure" otherwise.
        * result = "error" if any exception is caught

    """
    function_name = inspect.stack()[0][3]
    logger.debug(f"Start {function_name} check for host {device.host}")
    result = TestResult(host=str(device.host), test=function_name)

    if not number:
        result.is_skipped(
            "verify_bgp_rtc_count could not run because number was not supplied"
        )
        return result

    try:
        response = device.session.runCmds(1, ["show bgp rt-membership summary"], "json")
        logger.debug(f"query result is: {response}")

        peers = response[0]["vrfs"]["default"]["peers"]
        non_established_peers = [
            peer
            for peer, peer_dict in peers.items()
            if peer_dict["peerState"] != "Established"
        ]

        if not non_established_peers and len(peers) == number:
            result.is_success()
        else:
            result.is_failure()
            if len(peers) != number:
                result.is_failure(
                    f"Expecting {number} BGP RTC peers and got {len(peers)}"
                )

    except (jsonrpc.AppError, KeyError, socket.timeout) as e:
        logger.error(
            f"exception raised for {inspect.stack()[0][3]} -  {device.host}: {str(e)}"
        )
        result.is_error(str(e))
    return result
