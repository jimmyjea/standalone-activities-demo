# Module 02: Webhook retries

This module keeps the checkout flow from Module 01 but demonstrates automatic
Activity retries:

```text
Attempt 1 → webhook returns 503
Attempt 2 → webhook returns 503
Attempt 3 → webhook returns 200 → confirmation appears
```

Choose **02 · Webhook retries** from the checkout page. The confirmation page
shows all three calls as they happen. The Activity reads its durable attempt
number from `activity.info().attempt` and includes it in the webhook request.
The mock receiver fails attempts below three.

The retry policy uses a one-second initial interval, exponential backoff, and a
maximum of five attempts. No retry loop exists in application code.

## Suggested talk track

1. The checkout path is unchanged: it starts a Standalone Activity and returns.
2. The first webhook call receives a simulated HTTP 503.
3. The exception escapes the Activity; the Worker does not retry it itself.
4. Temporal records the failure and dispatches a new Activity attempt.
5. Attempt three succeeds, while the same business Activity ID and idempotency
   key are retained across every call.

Use the same server, Worker, and web app commands from
[Module 01](../01-checkout-confirmation/README.md).
