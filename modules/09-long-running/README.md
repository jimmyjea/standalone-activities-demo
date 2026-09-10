# Module 09: Long-running Activity rehydration

This module demonstrates resuming a long-running Standalone Activity from
heartbeat details after a Worker failure:

```text
Generate → send confirmation → heartbeat checkpoint → repeat
                          ↓ kill Worker
             bring Worker back → resume after checkpoint → 40 sent
```

Choose **09 · Long-running jobs** and click **Batch Confirmations**.
Temporal starts one `send_batched_confirmations` Standalone Activity. Each
second it records one confirmation and heartbeats the cumulative count. An
uninterrupted run sends 40 confirmations in 40 seconds.

Use **Kill Worker** while processing is underway, then click **Bring Worker
Back**. After the heartbeat timeout, Temporal dispatches a retry to the new
Worker. The Activity reads the last heartbeat details and continues with the
next unsent batch.

Confirmation writes are idempotent. If a Worker dies after writing a batch but
before its heartbeat reaches Temporal, retrying that batch does not create
duplicates.

The Activity uses:

- Start-to-close timeout: 30 seconds
- Heartbeat timeout: 3 seconds
- Retry interval: 1 second
- Maximum attempts: 10
