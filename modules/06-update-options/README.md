# Module 06: Update Activity options

This module demonstrates changing a Standalone Activity's options before its
first dispatch:

```text
Place order → 10-second start delay
                       ↓ update options
              5-second start delay → Worker dispatch → confirmation
```

Choose **06 · Update Activity options** on the checkout page, then click
**Update start delay to 5s** before the Activity starts. Temporal updates the
existing Activity Execution; the application does not cancel and reschedule
it.

The updated delay is measured from the Activity's original schedule time, as
defined by Temporal. Updating after five seconds therefore makes the Activity
available immediately.

## Prerelease requirement

Start-delay updates currently require the prerelease Temporal Server and CLI.
The Python SDK can schedule the initial delay but does not yet expose the
prerelease `UpdateActivityOptions` RPC, so this demo invokes the prerelease CLI
for the operator action.

Set `TEMPORAL_CLI_PATH` if the prerelease CLI is not located at
`../temporal-cli-prerelease/temporal` relative to this repository:

```bash
export TEMPORAL_CLI_PATH=/path/to/prerelease/temporal
```
