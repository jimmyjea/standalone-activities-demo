# Temporal Standalone Activities Demo

A set of small, independent modules for demonstrating Temporal's Standalone
Activities primitive. Standalone Activities are currently **Public Preview**.

## Modules

1. [`01-checkout-confirmation`](modules/01-checkout-confirmation/README.md) —
   checkout returns immediately while a durable Standalone Activity sends a
   confirmation through a webhook.
2. [`02-webhook-retries`](modules/02-webhook-retries/README.md) — the same UI
   makes the webhook fail twice and visualizes Temporal succeeding on the third
   Activity attempt.
3. [`03-pause-unpause`](modules/03-pause-unpause/README.md) — an operator pauses
   a failing Standalone Activity, repairs the downstream system, and unpauses
   it. This module requires the prerelease Server described in its README.
4. [`04-reset`](modules/04-reset/README.md) — an operator deploys a downstream
   fix and resets a repeatedly failing Standalone Activity.
5. [`05-start-delay`](modules/05-start-delay/README.md) — Temporal delays
   dispatch for ten seconds, leaving a cancellation window before execution.
6. [`06-update-options`](modules/06-update-options/README.md) — an operator
   updates a scheduled Activity's start delay from ten seconds to five.

## Prerequisites

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/)
- Temporal CLI 1.7.0+ (bundling Temporal Server 1.31.0+)

Check your local version:

```bash
temporal --version
```

Install the Python environment from this directory:

```bash
uv sync
```

The checkout page has a module dropdown, so all modules run in one browser
session. Each module also has its own demo narrative.
