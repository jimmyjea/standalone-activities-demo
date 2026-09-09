# Module 01: Checkout confirmation

This module shows a single durable job without a Workflow:

```text
Browser → Checkout API → Temporal Standalone Activity → Worker → Webhook
   └──────────── polls order status ────────────────────────────────┘
```

The API uses `Client.start_activity()` and redirects immediately. The
confirmation page then shows the Activity moving from queued to delivered and
renders the webhook payload in a mock inbox.

## Run it

Follow the shared setup in the [parent README](../../README.md), then select
**01 · Basic confirmation**, place the demo order, and watch the confirmation
receipt arrive.

The Temporal UI is at [http://localhost:8233](http://localhost:8233). The
Standalone Activity ID uses a business key such as
`send-confirmation:DEMO-A1B2C3D4`.

## Suggested talk track

1. Checkout receives the order and starts one Activity directly from the
   Temporal Client—there is no wrapper Workflow.
2. `start_activity()` returns after durable scheduling, so the customer can
   reach the confirmation page without waiting on delivery.
3. A Worker picks up the Activity and calls a real HTTP webhook.
4. The receiver deduplicates on Activity ID because Activities execute
   at-least-once by default.
5. Stop the Worker before checkout, place an order, then restart it to show the
   queued job completing.

## Configuration

Temporal connection settings are loaded through `ClientConfig`, so standard
Temporal environment variables and profiles work. The webhook defaults to the
local web app and can be overridden:

```bash
export CONFIRMATION_WEBHOOK_URL=https://example.test/confirmation
```

Reset the local demo data by deleting
`modules/01-checkout-confirmation/data/demo.db`.
