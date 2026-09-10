# Module 05: Start delay

This module demonstrates a server-side start delay for a Standalone Activity:

```text
Place order → Activity scheduled → 60-second delay → Worker dispatch → confirmation
                                  ↘ cancel before dispatch
```

Choose **05 · Start delay** on the checkout page. Temporal durably schedules
the confirmation with `start_delay=timedelta(seconds=60)`.
The confirmation page displays the remaining delay and allows cancellation
until a Worker receives the first Activity task.

If no one cancels, Temporal dispatches the Activity after 60 seconds and the
webhook delivers the order confirmation. Cancellation is sent to Temporal's
Standalone Activity API; the application does not use a local timer to prevent
execution.
