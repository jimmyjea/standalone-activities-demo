import asyncio
import hashlib

import httpx
from temporalio import activity

from .models import SendConfirmationInput


@activity.defn
async def send_order_confirmation(input: SendConfirmationInput) -> dict[str, str]:
    """Send an order confirmation to a webhook-backed mock delivery provider."""
    attempt = activity.info().attempt
    activity.logger.info("Sending confirmation for order %s to %s", input.order_id, input.recipient)

    # A short pause makes the durable background handoff visible during the demo.
    await asyncio.sleep(1.5)

    # Keep the provider ID stable across Activity retries.
    provider_message_id = "msg_" + hashlib.sha256(input.activity_id.encode()).hexdigest()[:12]
    payload = {
        "activity_id": input.activity_id,
        "order_id": input.order_id,
        "demo_mode": "standard",
        "recipient": input.recipient,
        "subject": f"Order {input.order_id} confirmed",
        "message": (
            f"Hi {input.customer_name}, your order for {input.total} is confirmed "
            "and being prepared."
        ),
        "provider_message_id": provider_message_id,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            input.webhook_url,
            json=payload,
            headers={
                "Idempotency-Key": input.activity_id,
                "X-Temporal-Attempt": str(attempt),
            },
        )
        response.raise_for_status()

    activity.logger.info("Confirmation delivered as %s", provider_message_id)
    return {
        "order_id": input.order_id,
        "provider_message_id": provider_message_id,
        "status": "delivered",
    }
