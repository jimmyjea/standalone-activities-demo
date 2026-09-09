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
