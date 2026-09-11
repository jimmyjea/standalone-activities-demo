# Module 03: Operator pause and unpause

This module demonstrates Temporal's native Activity pause controls during a
downstream incident:

```text
Activity retries every second → operator pauses → bug is fixed
                         → operator unpauses → runs 5 seconds → success
```

Choose **03 · Operator pause / unpause** on the checkout page. The confirmation
page includes a separate operations console. Click **Pause Activity & fix bug**,
observe that attempts stop, and then click **Unpause Activity** to complete the
delivery after a five-second successful run.

The retry policy is:

- Initial interval: 1 second
- Backoff coefficient: 1
- Maximum attempts: 20

## Prerelease requirement

This module uses a true Standalone Activity and the prerelease
`PauseActivityExecution` and `UnpauseActivityExecution` APIs. Stable Server
1.31.2 does not implement these APIs.

Build the current prerelease CLI, then enable Standalone Activity operator
commands on its embedded Server:

```bash
git clone https://github.com/temporalio/cli temporal-cli-prerelease
cd temporal-cli-prerelease
make build
./temporal server start-dev \
  --dynamic-config-value history.enableStandaloneActivityOperatorCommands=true
```

Use this server instead of the stable `temporal server start-dev` process.
The demo's pause and unpause controls call Temporal's real Standalone Activity
operator APIs; they are not simulated by the application.

## Suggested talk track

1. A downstream bug makes every confirmation attempt return HTTP 503.
2. Temporal retries once per second without exponential backoff.
3. The operator pauses the specific Standalone Activity Execution. No new
   attempts are dispatched while it is paused.
4. The pause action also represents repairing the downstream system.
5. Unpause dispatches the next attempt, which runs for five seconds and
   succeeds without changing the Activity input.

Use the same server, Worker, and web app commands from
[Module 01](../01-checkout-confirmation/README.md). Restart the Worker after
adding this module so it registers the Workflow and Activity definitions.
