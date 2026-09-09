# Module 11: Reuse a Standalone Activity in a Workflow

Activity definitions are not intrinsically standalone or Workflow-only. The
same implementation can be invoked directly by a Client or scheduled by a
Workflow.

Choose **11 · Reuse Activity in Workflow** and place an order through the
standard checkout page. The `FulfillmentWorkflow` runs:

1. `check_inventory` — mocked fulfillment Activity
2. `process_payment` — mocked fulfillment Activity
3. `prepare_shipment` — mocked fulfillment Activity
4. `send_order_confirmation` — the same implementation used as a Standalone
   Activity in Module 01

The first three steps each take one second. The confirmation Activity calls the
same idempotent webhook and populates the mock inbox. A Workflow query reports
completed steps to the confirmation page while execution is in progress.
