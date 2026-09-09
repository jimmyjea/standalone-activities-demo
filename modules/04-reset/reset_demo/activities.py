import asyncio
import hashlib

import httpx
from checkout_demo.models import SendConfirmationInput
from temporalio import activity


@activity.defn(name="send_resettable_confirmation")
async def send_resettable_confirmation(
    input: SendConfirmationInput,
) -> dict[str, str | int]:
    """Retry a broken downstream call until an operator fixes and resets it."""
    attempt = activity.info().attempt
    status_url = input.webhook_url.replace(
        "/api/webhooks/confirmation",
        f"/api/downstream/{input.order_id}/status",
    )
    async with httpx.AsyncClient(timeout=10) as client:
        status_response = await client.get(status_url)
        status_response.raise_for_status()
        bug_fixed = status_response.json()["bug_fixed"]

    if bug_fixed:
        await asyncio.sleep(5)
    else:
        await asyncio.sleep(0.3)

    provider_message_id = "msg_" + hashlib.sha256(input.activity_id.encode()).hexdigest()[:12]
    payload = {
        "activity_id": input.activity_id,
        "order_id": input.order_id,
        "demo_mode": "reset",
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
