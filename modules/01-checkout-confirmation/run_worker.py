import asyncio
import importlib
import sys
from pathlib import Path

from checkout_demo.activities import send_order_confirmation
from checkout_demo.temporal import TASK_QUEUE, get_temporal_client
from temporalio.worker import Worker

RETRY_MODULE_ROOT = Path(__file__).resolve().parents[1] / "02-webhook-retries"
sys.path.insert(0, str(RETRY_MODULE_ROOT))
send_confirmation_with_retries = importlib.import_module(
    "retry_demo.activities"
).send_confirmation_with_retries


async def main() -> None:
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        activities=[send_order_confirmation, send_confirmation_with_retries],
    )
    print(f"Confirmation worker polling {TASK_QUEUE!r}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
