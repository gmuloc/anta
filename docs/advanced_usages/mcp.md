<!--
  ~ Copyright (c) 2023-2026 Arista Networks, Inc.
  ~ Use of this source code is governed by the Apache License 2.0
  ~ that can be found in the LICENSE file.
  -->

# ANTA MCP Server

ANTA can run as a local [Model Context Protocol](https://modelcontextprotocol.io/) server for tools that support MCP.

The MCP server is optional and is not installed with the base ANTA library.

```bash
pip install anta[mcp]
```

## Run the Server

The first supported transport is local stdio:

```bash
anta-mcp --transport stdio
```

The server writes MCP protocol messages on stdout. Logs should go to stderr or a file:

```bash
anta-mcp --transport stdio --log-file anta-mcp.log --log-level INFO
```

## Credentials

The MCP server does not accept passwords in tool arguments. Set credentials with environment variables:

```bash
export ANTA_USERNAME=admin
export ANTA_PASSWORD='password'
export ANTA_ENABLE_PASSWORD='enable-password'
```

`ANTA_ENABLE_PASSWORD` is only needed when running tools with privileged mode enabled.

## File Access

By default, the MCP server can only read inventory and catalog files under the current working directory.

To allow more roots, set `ANTA_MCP_ALLOWED_PATHS` with the platform path separator:

```bash
export ANTA_MCP_ALLOWED_PATHS="/path/to/lab:/path/to/catalogs"
```

## Tools

The initial ANTA MCP server exposes safe NRFU workflows:

- `anta_validate_inventory`: parse an inventory file and return device metadata without connecting to devices.
- `anta_validate_catalog`: parse a catalog file and return test metadata.
- `anta_plan_nrfu_run`: perform an ANTA dry-run and return selected devices, scheduled tests, filters, and warnings.
- `anta_run_nrfu`: execute ANTA tests and store the results in MCP process memory.
- `anta_get_nrfu_results`: page and filter stored results.
- `anta_list_runs`: list stored runs in the current MCP process.
- `anta_clear_run`: delete one stored run from memory.

Result pages default to 50 results and are capped at 500 results.

## Future Streamable HTTP Support

The server is structured so the tool registration is separate from the transport. A future release can add:

```bash
anta-mcp --transport streamable-http --host 127.0.0.1 --port 8765
```

HTTP support must include bearer-token authentication, host/origin validation, request limits, and safe defaults before remote bind addresses are supported.
