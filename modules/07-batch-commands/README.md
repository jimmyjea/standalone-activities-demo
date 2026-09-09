# Module 07: Batch operator commands

This module demonstrates applying one operator command to many Standalone
Activities:

```text
Generate batch → 10 long-running Activities → select in Temporal UI
                                              ↓ batch cancel
                                      10 Cancel Requested states
```

Choose **07 · Batch operator commands** and click **Generate Activities**.
Each Activity can run for 10 minutes and heartbeats once per second. In Temporal
UI, filter by the shared `batch-long-running:<order-id>:` Activity ID prefix,
select all 10, and request cancellation.

After all cancellation requests are visible, the demo displays the equivalent
CLI command using the same visibility query:

```bash
temporal activity cancel \
  --query 'ActivityId STARTS_WITH "batch-long-running:<order-id>:"' \
  --reason "Cancel demo batch" \
  --yes
```

## Cancellation semantics

Cancellation is cooperative. Each Activity heartbeat receives Temporal's
cancellation response, raises a cancellation exception, and transitions the
execution from **Cancel Requested** to **Canceled**.

Standalone Activities and batch Activity operator commands are prerelease
features in this demo.
