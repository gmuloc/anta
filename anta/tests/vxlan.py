"""
Test functions related to VXLAN
"""
import inspect
import logging
import socket

from jsonrpclib import jsonrpc
from anta.inventory.models import InventoryDevice
from anta.result_manager.models import TestResult

logger = logging.getLogger(__name__)


def verify_vxlan(device: InventoryDevice) -> TestResult:
    """
    Verifies the interface vxlan 1 status is up/up.

    Args:
        device (InventoryDevice): InventoryDevice instance containing all devices information.

    Returns:
        TestResult instance with
        * result = "unset" if the test has not been executed
        * result = "success" if vxlan1 interface is UP UP
        * result = "failure" otherwise.
        * result = "error" if any exception is caught

    """
    function_name = inspect.stack()[0][3]
    logger.debug(f"Start {function_name} check for host {device.host}")
    result = TestResult(host=str(device.host), test=function_name)

    try:
        response = device.session.runCmds(1, ["show interfaces description"], "json")
        logger.debug(f"query result is: {response}")

        response_data = response[0]["interfaceDescriptions"]

        if "Vxlan1" not in response_data:
            result.is_failure("No interface VXLAN 1 detected.")
        else:
            protocol_status = response_data["Vxlan1"]["lineProtocolStatus"]
            interface_status = response_data["Vxlan1"]["intefraceStatus"]
            if protocol_status == "up" and interface_status == "up":
                result.is_success()
            else:
                result.messages.append(
                    f"Vxlan interface is {protocol_status}/{interface_status}."
                )

    except (jsonrpc.AppError, KeyError, socket.timeout) as e:
        logger.error(
            f"exception raised for {inspect.stack()[0][3]} -  {device.host}: {str(e)}"
        )
        result.is_error(str(e))

    return result


def verify_vxlan_config_sanity(device: InventoryDevice) -> TestResult:
    """
    Verifies there is no VXLAN config-sanity warnings.

    Args:
        device (InventoryDevice): InventoryDevice instance containing all devices information.

    Returns:
        TestResult instance with
        * result = "unset" if the test has not been executed
        * result = "success" if VXLAN config sanity is OK
        * result = "failure" otherwise.
        * result = "error" if any exception is caught
    """
    function_name = inspect.stack()[0][3]
    logger.debug(f"Start {function_name} check for host {device.host}")
    result = TestResult(host=str(device.host), test=function_name)

    try:
        response = device.session.runCmds(1, ["show vxlan config-sanity"], "json")
        logger.debug(f"query result is: {response}")
        response_data = response[0]["categories"]

        if len(response_data) == 0:
            result.is_skipped("Vxlan is not enabled on this device")
            return result

        failed_categories = {
            category: content
            for category, content in response_data.items()
            if category in ["localVtep", "mlag"] and content["allCheckPass"] is not True
        }

        if failed_categories:
            result.is_failure(
                f"Vxlan config sanity check is not passing: {failed_categories}"
            )
        else:
            result.is_success()

    except (jsonrpc.AppError, KeyError, socket.timeout) as e:
        logger.error(
            f"exception raised for {inspect.stack()[0][3]} -  {device.host}: {str(e)}"
        )
        result.is_error(str(e))

    return result
