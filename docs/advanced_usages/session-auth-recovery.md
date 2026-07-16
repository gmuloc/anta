---
title: Session Authentication Recovery
hide:
  - tags
tags:
  - eAPI
  - Session Authentication
---

<!--
  ~ Copyright (c) 2026 Arista Networks, Inc.
  ~ Use of this source code is governed by the Apache License 2.0
  ~ that can be found in the LICENSE file.
  -->

This page documents the session authentication recovery behavior implemented in ANTA's `asynceapi` client.

## Problem

When eAPI session authentication is enabled, ANTA reuses an EOS `Session` cookie across requests. With high concurrency, many requests can be sent with a cookie that is valid at dispatch time. EOS may then expire the session while those requests are still queued or processing on the device.

In that case, multiple in-flight requests can return `401 Session Expired`. Without recovery, each affected ANTA command collection fails. If there are no later commands to send, no later request exists to trigger a new login.

## Recovery behavior

`asynceapi.Device.jsonrpc_exec()` replays a JSON-RPC request once when the command request fails because the session cookie expired.

- A `401` returned by `/command-api` is treated as a command-phase authentication failure.
- The failed JSON-RPC request is retried exactly once.
- The retry uses the normal session-auth flow, so it logs in again when the stale cookie has been cleared.
- A `401` returned by `/login` is treated as a login-phase authentication failure and is not retried.
- A stale `401` response only clears the cookie that was attached to that request. It cannot clear a newer cookie created by another recovery.
- Concurrent stale-cookie failures serialize recovery to avoid independent login storms.

## Corner cases to test

Test these scenarios when changing session authentication behavior:

- A single command request returns `401`, re-login succeeds, and the replayed JSON-RPC request succeeds.
- Several in-flight command requests return `401` for the same stale cookie and replay successfully with one shared recovery login.
- A stale `401` for cookie A arrives after cookie B has been created and does not clear cookie B.
- `/login` returns `401` because credentials or authorization are wrong; the request is not replayed.
- A recovery login fails; later requests on the same client fail fast instead of repeatedly trying `/login`.
- Session authentication is disabled; HTTP `401` keeps the normal `httpx.HTTPStatusError` behavior.

## How to test

Use unit tests with mocked HTTP routes to keep the behavior deterministic:

- Mock `/login` with `respx` and return distinct `Set-Cookie` values to prove that replay uses the newer cookie.
- Mock `/command-api` to return `401` for requests carrying the stale cookie and `200` for requests carrying the recovered cookie.
- For concurrency tests, block stale-cookie responses until every expected in-flight request has reached `/command-api`, then release them together.
- Verify route call counts so one recovery does not become a login storm.

For lab validation, use a short EOS session lifetime and run many concurrent read-only `show` commands with `use_session_auth` enabled. Confirm that commands sent before expiry can recover by replaying once after re-login.

## Remaining limitations

Recovery is intentionally conservative:

- Each JSON-RPC request is replayed at most once.
- Bad credentials or an EOS authorization failure on `/login` are not recoverable.
- If a replayed request also outlives the new session, it can still fail.
- Replay is safest for read-only commands. Avoid relying on replay for non-idempotent commands where EOS could have executed the command before returning `401`.
