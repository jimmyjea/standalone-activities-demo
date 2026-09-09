# Module 04: Operator reset

This module demonstrates the prerelease Standalone Activity reset API:

```text
Attempt 1 fails → attempt 2 fails → attempts continue
                                      ↓ operator deploys fix and resets
Reset attempt 1 → repaired 5-second call → success
```

Choose **04 · Operator reset** on the checkout page. Once the downstream issue
causes a failed attempt, use the separate operations console to click
**Fix bug & reset Activity** while retries continue.

Reset restarts the same Activity Execution, returns its attempt count to one,
and re-arms its per-attempt timeouts. The operator action repairs the mocked
downstream system immediately before invoking Temporal's
`ResetActivityExecution` API. Temporal clears the prior attempt sequence and
dispatches reset attempt one, which completes after five seconds.

## Retry policy

- Initial interval: 1 second
- Backoff coefficient: 1
- Maximum attempts: 20
- Start-to-close timeout: 45 seconds

## Prerelease requirement

This module requires the same prerelease Server and
`history.enableStandaloneActivityOperatorCommands=true` configuration as
[Module 03](../03-pause-unpause/README.md).

The reset is performed by Temporal; it is not an application-level
re-scheduling simulation.

Resetting a terminal `FAILED` Standalone Activity is not supported by the
current prerelease Server. Reset must occur while the Activity is running,
paused, or waiting for another retry.
