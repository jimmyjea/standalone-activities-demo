import asyncio
import hashlib

import httpx
from checkout_demo.models import SendConfirmationInput
from temporalio import activity


@activity.defn(name="send_confirmation_with_retries")
async def send_confirmation_with_retries(
    input: SendConfirmationInput,
) -> dict[str, str | int]:
    """Call a webhook that intentionally fails its first two attempts."""
    attempt = activity.info().attempt
    activity.logger.info(
        "Calling confirmation webhook for order %s (attempt %d)",
        input.order_id,
        attempt,
    )
    await asyncio.sleep(0.8)

    provider_message_id = "msg_" + hashlib.sha256(input.activity_id.encode()).hexdigest()[:12]
    payload = {
        "activity_id": input.activity_id,
        "order_id": input.order_id,
        "demo_mode": "retry",
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

    return {
        "order_id": input.order_id,
        "provider_message_id": provider_message_id,
        "status": "delivered",
        "attempt": attempt,
    }
