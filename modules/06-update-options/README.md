# Module 06: Update Activity options

This module demonstrates changing a running Standalone Activity's retry policy:

```text
Attempt 1 fails → retries continue with maximum attempts = 20
                              ↓ update options
                   maximum attempts = 5 → terminal failure
```

Choose **06 · Update Activity options** on the checkout page, then click
**Set maximum attempts to 5** while the Activity is retrying. Temporal updates
the existing Activity Execution; the application does not cancel and
reschedule it.

The downstream webhook continues returning HTTP 503. Once attempt five fails,
Temporal applies the updated limit and stops retrying.

## Prerelease requirement

Activity option updates currently require the prerelease Temporal Server and
CLI. The Python SDK does not yet expose the prerelease
`UpdateActivityOptions` RPC, so this demo invokes the prerelease CLI for the
operator action.

Set `TEMPORAL_CLI_PATH` if the prerelease CLI is not located at
`../temporal-cli-prerelease/temporal` relative to this repository:

```bash
export TEMPORAL_CLI_PATH=/path/to/prerelease/temporal
```
