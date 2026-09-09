from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from checkout_demo.activities import send_order_confirmation
    from checkout_demo.models import SendConfirmationInput

    from fulfillment_demo.activities import (
        check_inventory,
        prepare_shipment,
        process_payment,
    )


@workflow.defn
class FulfillmentWorkflow:
    def __init__(self) -> None:
        self.completed_steps: list[str] = []

    @workflow.run
    async def run(self, input: SendConfirmationInput) -> dict[str, str]:
        for step, activity_function in (
            ("inventory", check_inventory),
            ("payment", process_payment),
            ("shipment", prepare_shipment),
        ):
            await workflow.execute_activity(
                activity_function,
                input.order_id,
                start_to_close_timeout=timedelta(seconds=10),
            )
            self.completed_steps.append(step)

        result = await workflow.execute_activity(
            send_order_confirmation,
            input,
            start_to_close_timeout=timedelta(seconds=20),
        )
        self.completed_steps.append("confirmation")
        return result

    @workflow.query
    def progress(self) -> list[str]:
        return self.completed_steps
