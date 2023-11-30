# Copyright (c) 2023 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the LICENSE file.
# pylint: disable = redefined-outer-name
"""
Commands for Anta CLI to run check commands.
"""
from __future__ import annotations

import logging

import click
from rich.pretty import pretty_repr

from anta.catalog import AntaCatalog
from anta.cli.console import console
from anta.cli.utils import catalog_options

logger = logging.getLogger(__name__)


@click.command
@catalog_options
def catalog(catalog: AntaCatalog) -> None:
    """
    Check that the catalog is valid
    """
    console.print(f"[bold][green]Catalog {catalog.filename} is valid")
    console.print(pretty_repr(catalog.tests))
