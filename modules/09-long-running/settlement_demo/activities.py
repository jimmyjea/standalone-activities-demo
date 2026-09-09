import asyncio

import httpx
from checkout_demo.models import BatchConfirmationInput
from temporalio import activity


@activity.defn(name="send_batched_confirmations")
async def send_batched_confirmations(
    input: BatchConfirmationInput,
) -> dict[str, int | str]:
    """Send 20 confirmations in resumable batches of two."""
    heartbeat_details = activity.info().heartbeat_details
    confirmed_count = (
        int(heartbeat_details[0].get("confirmed_count", 0))
        if heartbeat_details
        else 0
    )

    while confirmed_count < 20:
        await asyncio.sleep(1)
        next_count = min(confirmed_count + 2, 20)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                input.batch_url,
                json={
                    "activity_id": input.activity_id,
                    "first_confirmation": confirmed_count + 1,
                    "last_confirmation": next_count,
                },
            )
            response.raise_for_status()
        confirmed_count = next_count
        activity.heartbeat({"confirmed_count": confirmed_count})

    return {
        "order_id": input.order_id,
        "confirmed_count": confirmed_count,
        "status": "completed",
    }
