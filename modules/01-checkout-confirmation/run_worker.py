import asyncio
import importlib
import sys
from pathlib import Path

from checkout_demo.activities import send_order_confirmation
from checkout_demo.temporal import TASK_QUEUE, get_temporal_client
from temporalio.worker import Worker

RETRY_MODULE_ROOT = Path(__file__).resolve().parents[1] / "02-webhook-retries"
PAUSE_MODULE_ROOT = Path(__file__).resolve().parents[1] / "03-pause-unpause"
RESET_MODULE_ROOT = Path(__file__).resolve().parents[1] / "04-reset"
DELAY_MODULE_ROOT = Path(__file__).resolve().parents[1] / "05-start-delay"
UPDATE_MODULE_ROOT = Path(__file__).resolve().parents[1] / "06-update-options"
BATCH_MODULE_ROOT = Path(__file__).resolve().parents[1] / "07-batch-commands"
SEARCH_MODULE_ROOT = Path(__file__).resolve().parents[1] / "08-search-attributes"
sys.path.insert(0, str(RETRY_MODULE_ROOT))
sys.path.insert(0, str(PAUSE_MODULE_ROOT))
sys.path.insert(0, str(RESET_MODULE_ROOT))
sys.path.insert(0, str(DELAY_MODULE_ROOT))
sys.path.insert(0, str(UPDATE_MODULE_ROOT))
sys.path.insert(0, str(BATCH_MODULE_ROOT))
sys.path.insert(0, str(SEARCH_MODULE_ROOT))
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
        ],
    )
    print(f"Confirmation worker polling {TASK_QUEUE!r}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
