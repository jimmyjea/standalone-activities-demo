# Module 08: Search Attributes

This module demonstrates filtering Standalone Activities through visibility:

```text
Generate 10 Activities → 5 complete immediately
                       ↘ 5 remain running → filter → cancel
```

Choose **08 · Search Attributes** and click **Generate Activities**. Five
randomly selected Activities complete immediately. The other five run for up
to 10 minutes, heartbeat once per second, and support cooperative
cancellation.

Use Temporal UI to filter for running executions and cancel the remaining
five. Once all cancellation responses have been received, the demo displays
the equivalent CLI command:

```bash
temporal activity cancel \
  --query 'ExecutionStatus = "Running"' \
  --reason "Cancel running Activities" \
  --yes
```

`ExecutionStatus` is a built-in Search Attribute. Applications can also attach
custom Search Attributes when starting Activities, enabling visibility queries
based on business-specific metadata such as customer, region, or job category.
