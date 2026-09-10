# Module 10: Task Queue fairness

This module demonstrates weighted Task Queue fairness with Standalone
Activities:

```text
t=0s   Small merchant: 20 confirmations, weight 1
       Large merchant: 40 confirmations, weight 2
       Shared three-slot Worker → weighted fair dispatch
```

Choose **10 · Task Queue fairness** and click **Send Confirmations for Multiple
Merchants**. Ten small-merchant confirmations and twenty large-merchant
confirmations are scheduled together. Every confirmation takes two seconds.

Both merchants share the `checkout-confirmations` Task Queue and Worker used by
the other modules:

- Small merchant: fairness key `small-merchant`, weight `1`
- Large merchant: fairness key `large-merchant`, weight `2`

The dedicated Worker has three Activity slots, ensuring a backlog exists when
the large merchant's work arrives. Temporal gives the large merchant roughly
twice the dispatch share while continuing to process the small merchant, which
prevents starvation.

After processing completes, the UI also highlights related multitenant controls:
Priority, Task Queue dispatch rate limits, and Worker concurrency limits.

## Self-hosted configuration

Fairness is Public Preview and must be enabled on the local development server:

```bash
temporal server start-dev \
  --dynamic-config-value matching.useNewMatcher=true \
  --dynamic-config-value matching.enableFairness=true \
  --dynamic-config-value matching.enableMigration=true
```

Fairness is a paid feature in Temporal Cloud.
