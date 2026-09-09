import asyncio
import importlib
import os
import sys
from datetime import timedelta
from pathlib import Path

from checkout_demo.activities import send_order_confirmation
from checkout_demo.temporal import FAIRNESS_TASK_QUEUE, TASK_QUEUE, get_temporal_client
from temporalio.worker import Worker

RETRY_MODULE_ROOT = Path(__file__).resolve().parents[1] / "02-webhook-retries"
PAUSE_MODULE_ROOT = Path(__file__).resolve().parents[1] / "03-pause-unpause"
RESET_MODULE_ROOT = Path(__file__).resolve().parents[1] / "04-reset"
DELAY_MODULE_ROOT = Path(__file__).resolve().parents[1] / "05-start-delay"
UPDATE_MODULE_ROOT = Path(__file__).resolve().parents[1] / "06-update-options"
BATCH_MODULE_ROOT = Path(__file__).resolve().parents[1] / "07-batch-commands"
SEARCH_MODULE_ROOT = Path(__file__).resolve().parents[1] / "08-search-attributes"
SETTLEMENT_MODULE_ROOT = Path(__file__).resolve().parents[1] / "09-long-running"
FAIRNESS_MODULE_ROOT = Path(__file__).resolve().parents[1] / "10-fairness"
WORKFLOW_REUSE_MODULE_ROOT = Path(__file__).resolve().parents[1] / "11-activity-reuse"
WORKER_PID_PATH = Path(
    os.getenv(
        "DEMO_WORKER_PID_PATH",
        Path(__file__).resolve().parent / "data" / "worker.pid",
    )
)
sys.path.insert(0, str(RETRY_MODULE_ROOT))
sys.path.insert(0, str(PAUSE_MODULE_ROOT))
sys.path.insert(0, str(RESET_MODULE_ROOT))
sys.path.insert(0, str(DELAY_MODULE_ROOT))
sys.path.insert(0, str(UPDATE_MODULE_ROOT))
sys.path.insert(0, str(BATCH_MODULE_ROOT))
sys.path.insert(0, str(SEARCH_MODULE_ROOT))
sys.path.insert(0, str(SETTLEMENT_MODULE_ROOT))
sys.path.insert(0, str(FAIRNESS_MODULE_ROOT))
sys.path.insert(0, str(WORKFLOW_REUSE_MODULE_ROOT))
send_confirmation_with_retries = importlib.import_module(
    "retry_demo.activities"
).send_confirmation_with_retries
send_buggy_confirmation = importlib.import_module("pause_demo.activities").send_buggy_confirmation
send_resettable_confirmation = importlib.import_module(
    "reset_demo.activities"
).send_resettable_confirmation
send_delayed_confirmation = importlib.import_module(
    "delay_demo.activities"
).send_delayed_confirmation
send_updated_delay_confirmation = importlib.import_module(
    "update_demo.activities"
).send_updated_delay_confirmation
run_long_running_batch_activity = importlib.import_module(
    "batch_demo.activities"
).run_long_running_batch_activity
run_search_attribute_activity = importlib.import_module(
    "search_demo.activities"
).run_search_attribute_activity
send_batched_confirmations = importlib.import_module(
    "settlement_demo.activities"
).send_batched_confirmations
send_fairness_confirmation = importlib.import_module(
    "fairness_demo.activities"
).send_fairness_confirmation
fulfillment_activities = importlib.import_module("fulfillment_demo.activities")
FulfillmentWorkflow = importlib.import_module(
    "fulfillment_demo.workflows"
).FulfillmentWorkflow


async def main() -> None:
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        activities=[
            send_order_confirmation,
            send_confirmation_with_retries,
            send_buggy_confirmation,
            send_resettable_confirmation,
            send_delayed_confirmation,
            send_updated_delay_confirmation,
            run_long_running_batch_activity,
            run_search_attribute_activity,
            send_batched_confirmations,
            fulfillment_activities.check_inventory,
            fulfillment_activities.process_payment,
            fulfillment_activities.prepare_shipment,
        ],
        workflows=[FulfillmentWorkflow],
        max_heartbeat_throttle_interval=timedelta(milliseconds=500),
    )
    fairness_worker = Worker(
        client,
        task_queue=FAIRNESS_TASK_QUEUE,
        activities=[send_fairness_confirmation],
        max_concurrent_activities=3,
    )
    WORKER_PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    WORKER_PID_PATH.write_text(str(os.getpid()))
    print(
        f"Confirmation workers polling {TASK_QUEUE!r} and {FAIRNESS_TASK_QUEUE!r}"
    )
    try:
        await asyncio.gather(worker.run(), fairness_worker.run())
    finally:
        if (
            WORKER_PID_PATH.exists()
            and WORKER_PID_PATH.read_text().strip() == str(os.getpid())
        ):
            WORKER_PID_PATH.unlink()


if __name__ == "__main__":
    asyncio.run(main())
