"""
Test functions related to the EOS software
"""
from typing import List

from jsonrpclib import jsonrpc
from anta.inventory.models import InventoryDevice
from anta.result_manager.models import TestResult


def verify_eos_version(device: InventoryDevice, versions: List[str] = None) -> TestResult:
    """
    Verifies the device is running one of the allowed EOS version.

    Args:
        device (InventoryDevice): InventoryDevice instance containing all devices information.
        versions (list): List of allowed EOS versions.

    Returns:
        TestResult instance with
        * result = "unset" if test has not been executed
        * result = "success" if EOS version is valid against versions
        * result = "failure" otherwise.
        * result = "error" if any exception is caught

    """
    result = TestResult(host=str(device.host),
                        test="verify_eos_version")
    if not versions:
        result.result = "unset"
        result.messages.append(
            "verify_eos_version was not run as no "
            "versions were givem"
        )
        return result

    try:
        response = device.session.runCmds(1, ['show version'], 'json')
        if response[0]['version'] in versions:
            result.result = 'success'
        else:
            result.result = 'failure'
            result.messages.append(f'device is running version {response[0]["version"]} not in expected version')
    except (jsonrpc.AppError, KeyError) as e:
        result.messages.append(str(e))
        result.result = 'error'
    return result


def verify_terminattr_version(device: InventoryDevice, versions=None) -> TestResult:
    """
    Verifies the device is running one of the allowed TerminAttr version.

    Args:
        device (InventoryDevice): InventoryDevice instance containing all devices information.
        versions (list): List of allowed TerminAttr versions.

    Returns:
        TestResult instance with
        * result = "unset" if test has not been executed
        * result = "success" if TerminAttr version is valid against versions
        * result = "failure" otherwise.
        * result = "error" if any exception is caught
    """
    result = TestResult(host=str(device.host),
                        test="verify_terminattr_version")
    if not versions:
        result.result = "unset"
        result.messages.append(
            "verify_terminattr_version was not run as no "
            "versions were givem"
        )
        return result
    try:
        response = device.session.runCmds(1, ['show version detail'], 'json')
        response_data = response[0]['details']['packages']['TerminAttr-core']['version']
        if response_data in versions:
            result.result = 'success'
        else:
            result.result = 'failure'
            result.messages.append(f'device is running TerminAttr version {response_data} and is not in the allowed list')
    except (jsonrpc.AppError, KeyError) as e:
        result.messages.append(str(e))
        result.result = 'error'
    return result

def verify_eos_extensions(device: InventoryDevice) -> TestResult:
    """
    Verifies all EOS extensions installed on the device are enabled for boot persistence.

    Args:
        device (jsonrpclib.jsonrpc.ServerProxy): Instance of the class jsonrpclib.jsonrpc.ServerProxy with the uri f'https://{username}:{password}@{ip}/command-api'.
        enable_password (str): Enable password.

    Returns:
        bool: `True` if the device has all installed its EOS extensions enabled for boot persistence.
        `False` otherwise.

    """
    try:
        response = device.session.runCmds(1, ['show extensions', 'show boot-extensions'], 'json')
    except jsonrpc.AppError:
        return None
    installed_extensions = []
    boot_extensions = []
    try:
        for extension in response[0]['extensions']:
            if response[0]['extensions'][extension]['status'] == 'installed':
                installed_extensions.append(extension)
        for extension in response[1]['extensions']:
            extension = extension.strip('\n')
            if extension == '':
                pass
            else:
                boot_extensions.append(extension)
        installed_extensions.sort()
        boot_extensions.sort()
        if installed_extensions == boot_extensions:
            return True
        return False
    except KeyError:
        return None


def verify_field_notice_44_resolution(device: InventoryDevice) -> TestResult:
    """
    Verifies the device is using an Aboot version that fix the bug discussed
    in the field notice 44 (Aboot manages system settings prior to EOS initialization).

    Args:
        device (InventoryDevice): InventoryDevice instance containing all devices information.

    Returns:
        TestResult instance with
        * result = "unset" if test has not been executed
        * result = "success" if aboot is running valid version
        * result = "failure" otherwise.
        * result = "error" if any exception is caught
    """
    result = TestResult(host=str(device.host),
                        test="verify_field_notice_44_resolution")
    try:
        response = device.session.runCmds(1, ['show version detail'], 'json')
        devices = ['DCS-7010T-48',
                'DCS-7010T-48-DC',
                'DCS-7050TX-48',
                'DCS-7050TX-64',
                'DCS-7050TX-72',
                'DCS-7050TX-72Q',
                'DCS-7050TX-96',
                'DCS-7050TX2-128',
                'DCS-7050SX-64',
                'DCS-7050SX-72',
                'DCS-7050SX-72Q',
                'DCS-7050SX2-72Q',
                'DCS-7050SX-96',
                'DCS-7050SX2-128',
                'DCS-7050QX-32S',
                'DCS-7050QX2-32S',
                'DCS-7050SX3-48YC12',
                'DCS-7050CX3-32S',
                'DCS-7060CX-32S',
                'DCS-7060CX2-32S',
                'DCS-7060SX2-48YC6',
                'DCS-7160-48YC6',
                'DCS-7160-48TC6',
                'DCS-7160-32CQ',
                'DCS-7280SE-64',
                'DCS-7280SE-68',
                'DCS-7280SE-72',
                'DCS-7150SC-24-CLD',
                'DCS-7150SC-64-CLD',
                'DCS-7020TR-48',
                'DCS-7020TRA-48',
                'DCS-7020SR-24C2',
                'DCS-7020SRG-24C2',
                'DCS-7280TR-48C6',
                'DCS-7280TRA-48C6',
                'DCS-7280SR-48C6',
                'DCS-7280SRA-48C6',
                'DCS-7280SRAM-48C6',
                'DCS-7280SR2K-48C6-M',
                'DCS-7280SR2-48YC6',
                'DCS-7280SR2A-48YC6',
                'DCS-7280SRM-40CX2',
                'DCS-7280QR-C36',
                'DCS-7280QRA-C36S']
        variants = ['-SSD-F',
                    '-SSD-R',
                    '-M-F',
                    '-M-R',
                    '-F',
                    '-R']

        model = response[0]['modelName']
        for variant in variants:
            model = model.replace(variant, '')
        if model not in devices:
            result.result = 'unset'
            result.messages.append('device is not impacted by FN044')

        for component in response[0]['details']['components']:
            if component['name'] == 'Aboot':
                aboot_version = component['version'].split('-')[2]
        result.result = 'success'
        if aboot_version.startswith('4.0.') and int(aboot_version.split('.')[2]) < 7:
            result.result = 'failure'
            result.messages.append(
                f'device is running incorrect version of aboot ({aboot_version})')
        elif aboot_version.startswith('4.1.') and int(aboot_version.split('.')[2]) < 1:
            result.result = 'failure'
            result.messages.append(
                f'device is running incorrect version of aboot ({aboot_version})')
        elif aboot_version.startswith('6.0.') and int(aboot_version.split('.')[2]) < 9:
            result.result = 'failure'
            result.messages.append(
                f'device is running incorrect version of aboot ({aboot_version})')
        elif aboot_version.startswith('6.1.') and int(aboot_version.split('.')[2]) < 7:
            result.result = 'failure'
            result.messages.append(
                f'device is running incorrect version of aboot ({aboot_version})')
    except (jsonrpc.AppError, KeyError) as e:
        result.messages.append(str(e))
        result.result = 'error'
    return result
