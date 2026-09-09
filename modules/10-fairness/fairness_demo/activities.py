import asyncio

from checkout_demo.models import FairnessConfirmationInput
from temporalio import activity


@activity.defn(name="send_fairness_confirmation")
async def send_fairness_confirmation(
    input: FairnessConfirmationInput,
) -> dict[str, int | str]:
    """Simulate a confirmation that occupies one Worker slot for two seconds."""
    await asyncio.sleep(2)
    return {
        "activity_id": input.activity_id,
        "merchant": input.merchant,
        "confirmation_number": input.confirmation_number,
        "status": "completed",
    }
