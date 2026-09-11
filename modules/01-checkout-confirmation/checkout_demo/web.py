import asyncio
import os
import random
import signal
import subprocess
import sys
import uuid
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from temporalio.api.workflowservice.v1 import (
    DescribeActivityExecutionRequest,
    PauseActivityExecutionRequest,
    ResetActivityExecutionRequest,
    UnpauseActivityExecutionRequest,
)
from temporalio.common import Priority, RetryPolicy

from .activities import send_order_confirmation
from .models import (
    BatchConfirmationInput,
    CheckoutRequest,
    ConfirmationBatchRequest,
    ConfirmationWebhook,
    FairnessConfirmationInput,
    SearchAttributeJob,
    SendConfirmationInput,
)
from .store import DemoStore
from .temporal import TASK_QUEUE, get_temporal_client

MODULE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODULE_ROOT.parents[1]
STATIC_ROOT = MODULE_ROOT / "static"
RUN_WORKER_PATH = MODULE_ROOT / "run_worker.py"
WORKER_PID_PATH = Path(
    os.getenv("DEMO_WORKER_PID_PATH", MODULE_ROOT / "data" / "worker.pid")
)
ORDER_TOTAL = "$128.00"
# The prerelease Server returns PAUSED before the stable SDK names this enum value.
PAUSED_ACTIVITY_STATUS = 7
FAILED_ACTIVITY_STATUS = 3
RUNNING_ACTIVITY_STATUS = 1
CANCELED_ACTIVITY_STATUS = 4
COMPLETED_ACTIVITY_STATUS = 2
CANCEL_REQUESTED_RUN_STATE = 3
BATCH_SIZE = 10
LONG_RUNNING_CONFIRMATION_TOTAL = 40
FAIRNESS_SMALL_TOTAL = 20
FAIRNESS_LARGE_TOTAL = 40


def _search_attribute_jobs(order_id: str) -> list[SearchAttributeJob]:
    long_running_indexes = set(random.Random(order_id).sample(range(1, 11), 5))
    return [
        SearchAttributeJob(
            job_id=f"search-activity:{order_id}:{index:02}",
            long_running=index in long_running_indexes,
        )
        for index in range(1, 11)
    ]


def _fairness_jobs(order_id: str) -> list[FairnessConfirmationInput]:
    jobs: list[FairnessConfirmationInput] = []
    for index in range(1, FAIRNESS_SMALL_TOTAL + 1):
        jobs.append(
            FairnessConfirmationInput(
                activity_id=f"fairness:{order_id}:small:{index:02}",
                merchant="small",
                confirmation_number=index,
            )
        )
        jobs.extend(
            [
                FairnessConfirmationInput(
                    activity_id=f"fairness:{order_id}:large:{large_index:02}",
                    merchant="large",
                    confirmation_number=large_index,
                )
                for large_index in (index * 2 - 1, index * 2)
            ]
        )
    return jobs

app = FastAPI(title="Standalone Activities Checkout Demo")
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")
store = DemoStore()


@app.get("/", include_in_schema=False)
async def checkout_page() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")


@app.get("/confirmation", include_in_schema=False)
async def confirmation_page() -> FileResponse:
    return FileResponse(STATIC_ROOT / "confirmation.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/checkout", status_code=202)
async def checkout(request: CheckoutRequest) -> dict[str, str]:
    order_id = f"DEMO-{uuid.uuid4().hex[:8].upper()}"
    is_retry_demo = request.module == "webhook-retries"
    is_pause_demo = request.module == "pause-unpause"
    is_reset_demo = request.module == "reset"
    is_start_delay_demo = request.module == "start-delay"
    is_update_options_demo = request.module == "update-options"
    is_batch_demo = request.module == "batch-commands"
    is_search_attributes_demo = request.module == "search-attributes"
    is_long_running_demo = request.module == "long-running"
    is_fairness_demo = request.module == "fairness"
    is_workflow_reuse_demo = request.module == "workflow-reuse"
    if is_pause_demo:
        activity_id = f"pausable-confirmation:{order_id}"
    elif is_reset_demo:
        activity_id = f"reset-confirmation:{order_id}"
    elif is_start_delay_demo:
        activity_id = f"delayed-confirmation:{order_id}"
    elif is_update_options_demo:
        activity_id = f"options-confirmation:{order_id}"
    elif is_batch_demo:
        activity_id = f"batch-group:{order_id}"
    elif is_search_attributes_demo:
        activity_id = f"search-group:{order_id}"
    elif is_long_running_demo:
        activity_id = f"batched-confirmations:{order_id}"
    elif is_fairness_demo:
        activity_id = f"fairness-group:{order_id}"
    elif is_workflow_reuse_demo:
        activity_id = f"fulfillment-workflow:{order_id}"
    elif is_retry_demo:
        activity_id = f"retry-confirmation:{order_id}"
    else:
        activity_id = f"send-confirmation:{order_id}"
    webhook_url = os.getenv(
        "CONFIRMATION_WEBHOOK_URL",
        "http://127.0.0.1:8000/api/webhooks/confirmation",
    )
    activity_input = SendConfirmationInput(
        activity_id=activity_id,
        order_id=order_id,
        customer_name=request.customer_name.strip(),
        recipient=str(request.email),
        total=ORDER_TOTAL,
        webhook_url=webhook_url,
    )
    store.create_order(
        order_id=order_id,
        customer_name=request.customer_name.strip(),
        email=str(request.email),
        total=ORDER_TOTAL,
        activity_id=activity_id,
    )

    try:
        client = await get_temporal_client()
        if is_batch_demo:
            await asyncio.gather(
                *(
                    client.start_activity(
                        "run_long_running_batch_activity",
                        args=[f"batch-long-running:{order_id}:{index:02}"],
                        id=f"batch-long-running:{order_id}:{index:02}",
                        task_queue=TASK_QUEUE,
                        schedule_to_close_timeout=timedelta(minutes=15),
                        start_to_close_timeout=timedelta(minutes=10),
                        heartbeat_timeout=timedelta(seconds=5),
                        retry_policy=RetryPolicy(maximum_attempts=1),
                    )
                    for index in range(1, BATCH_SIZE + 1)
                )
            )
        elif is_workflow_reuse_demo:
            await client.start_workflow(
                "FulfillmentWorkflow",
                args=[activity_input],
                id=activity_id,
                task_queue=TASK_QUEUE,
                execution_timeout=timedelta(minutes=5),
            )
        elif is_fairness_demo:
            await asyncio.gather(
                *(
                    client.start_activity(
                        "send_fairness_confirmation",
                        args=[job],
                        id=job.activity_id,
                        task_queue=TASK_QUEUE,
                        schedule_to_close_timeout=timedelta(minutes=2),
                        start_to_close_timeout=timedelta(seconds=10),
                        retry_policy=RetryPolicy(maximum_attempts=1),
                        priority=Priority(
                            fairness_key=f"{job.merchant}-merchant",
                            fairness_weight=(
                                1.0 if job.merchant == "small" else 2.0
                            ),
                        ),
                    )
                    for job in _fairness_jobs(order_id)
                )
            )
        elif is_long_running_demo:
            await client.start_activity(
                "send_batched_confirmations",
                args=[
                    BatchConfirmationInput(
                        order_id=order_id,
                        activity_id=activity_id,
                        batch_url=os.getenv(
                            "CONFIRMATION_BATCH_URL",
                            f"http://127.0.0.1:8000/api/orders/{order_id}/confirmation-batch",
                        ),
                    )
                ],
                id=activity_id,
                task_queue=TASK_QUEUE,
                schedule_to_close_timeout=timedelta(minutes=2),
                start_to_close_timeout=timedelta(seconds=30),
                heartbeat_timeout=timedelta(seconds=3),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    backoff_coefficient=1,
                    maximum_attempts=10,
                ),
            )
        elif is_search_attributes_demo:
            await asyncio.gather(
                *(
                    client.start_activity(
                        "run_search_attribute_activity",
                        args=[job],
                        id=job.job_id,
                        task_queue=TASK_QUEUE,
                        schedule_to_close_timeout=timedelta(minutes=15),
                        start_to_close_timeout=timedelta(minutes=10),
                        heartbeat_timeout=(
                            timedelta(seconds=5) if job.long_running else None
                        ),
                        retry_policy=RetryPolicy(maximum_attempts=1),
                    )
                    for job in _search_attribute_jobs(order_id)
                )
            )
        elif is_pause_demo:
            await client.start_activity(
                "send_buggy_confirmation",
                args=[activity_input],
                id=activity_id,
                task_queue=TASK_QUEUE,
                schedule_to_close_timeout=timedelta(minutes=5),
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    backoff_coefficient=1,
                    maximum_attempts=20,
                ),
            )
        elif is_reset_demo:
            await client.start_activity(
                "send_resettable_confirmation",
                args=[activity_input],
                id=activity_id,
                task_queue=TASK_QUEUE,
                schedule_to_close_timeout=timedelta(minutes=5),
                start_to_close_timeout=timedelta(seconds=45),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    backoff_coefficient=1,
                    maximum_attempts=20,
                ),
            )
        elif is_start_delay_demo:
            await client.start_activity(
                "send_delayed_confirmation",
                args=[activity_input],
                id=activity_id,
                task_queue=TASK_QUEUE,
                start_delay=timedelta(seconds=60),
                schedule_to_close_timeout=timedelta(minutes=1),
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        elif is_update_options_demo:
            await client.start_activity(
                "send_updated_delay_confirmation",
                args=[activity_input],
                id=activity_id,
                task_queue=TASK_QUEUE,
                schedule_to_close_timeout=timedelta(minutes=5),
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    backoff_coefficient=1,
                    maximum_attempts=20,
                ),
            )
        else:
            activity_type = (
                "send_confirmation_with_retries" if is_retry_demo else send_order_confirmation
            )
            await client.start_activity(
                activity_type,
                args=[activity_input],
                id=activity_id,
                task_queue=TASK_QUEUE,
                schedule_to_close_timeout=timedelta(minutes=2),
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    backoff_coefficient=2,
                    maximum_attempts=5,
                ),
            )
        store.set_status(order_id, "queued")
    except Exception as error:
        store.set_status(order_id, "scheduling_failed", str(error))
        raise HTTPException(
            status_code=503,
            detail="Could not schedule the confirmation activity. Is Temporal running?",
        ) from error

    return {
        "order_id": order_id,
        "activity_id": activity_id,
        "confirmation_url": f"/confirmation?order_id={order_id}",
    }


@app.get("/api/orders/{order_id}")
async def get_order(order_id: str) -> dict:
    order = store.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["module"] == "workflow-reuse":
        client = await get_temporal_client()
        handle = client.get_workflow_handle(order["activity_id"])
        description = await handle.describe()
        order["workflow_status"] = int(description.status)
        if order["workflow_status"] == 2:
            order["workflow_steps"] = [
                "inventory",
                "payment",
                "shipment",
                "confirmation",
            ]
        else:
            order["workflow_steps"] = await handle.query("progress")
        return order
    if order["module"] == "batch-commands":
        activity_ids = [
            f"batch-long-running:{order_id}:{index:02}"
            for index in range(1, BATCH_SIZE + 1)
        ]
        descriptions = await asyncio.gather(
            *(_activity_info(activity_id) for activity_id in activity_ids)
        )
        order["batch_activities"] = [
            {
                "activity_id": activity_id,
                "status": info.status,
                "run_state": info.run_state,
            }
            for activity_id, info in zip(activity_ids, descriptions, strict=True)
        ]
        order["cancel_requested_count"] = sum(
            activity["run_state"] == CANCEL_REQUESTED_RUN_STATE
            or activity["status"] == CANCELED_ACTIVITY_STATUS
            for activity in order["batch_activities"]
        )
        order["canceled_count"] = sum(
            activity["status"] == CANCELED_ACTIVITY_STATUS
            for activity in order["batch_activities"]
        )
        order["all_cancellation_requested"] = (
            order["cancel_requested_count"] == BATCH_SIZE
        )
        order["all_canceled"] = order["canceled_count"] == BATCH_SIZE
        return order
    if order["module"] == "fairness":
        jobs = _fairness_jobs(order_id)
        descriptions = await asyncio.gather(
            *(_activity_info(job.activity_id) for job in jobs)
        )
        order["fairness_activities"] = [
            {
                "activity_id": job.activity_id,
                "merchant": job.merchant,
                "confirmation_number": job.confirmation_number,
                "status": info.status,
                "run_state": info.run_state,
                "started_at": (
                    info.last_started_time.ToDatetime().isoformat()
                    if info.HasField("last_started_time")
                    else None
                ),
                "closed_at": (
                    info.close_time.ToDatetime().isoformat()
                    if info.HasField("close_time")
                    else None
                ),
            }
            for job, info in zip(jobs, descriptions, strict=True)
        ]
        order["small_completed"] = sum(
            item["merchant"] == "small"
            and item["status"] == COMPLETED_ACTIVITY_STATUS
            for item in order["fairness_activities"]
        )
        order["large_completed"] = sum(
            item["merchant"] == "large"
            and item["status"] == COMPLETED_ACTIVITY_STATUS
            for item in order["fairness_activities"]
        )
        order["fairness_complete"] = (
            order["small_completed"] == FAIRNESS_SMALL_TOTAL
            and order["large_completed"] == FAIRNESS_LARGE_TOTAL
        )
        return order
    if order["module"] == "search-attributes":
        jobs = _search_attribute_jobs(order_id)
        descriptions = await asyncio.gather(
            *(_activity_info(job.job_id) for job in jobs)
        )
        order["search_activities"] = [
            {
                "activity_id": job.job_id,
                "long_running": job.long_running,
                "status": info.status,
                "run_state": info.run_state,
            }
            for job, info in zip(jobs, descriptions, strict=True)
        ]
        order["completed_count"] = sum(
            item["status"] == COMPLETED_ACTIVITY_STATUS
            for item in order["search_activities"]
        )
        order["canceled_count"] = sum(
            item["status"] == CANCELED_ACTIVITY_STATUS
            for item in order["search_activities"]
        )
        order["all_long_running_canceled"] = all(
            item["status"] == CANCELED_ACTIVITY_STATUS
            for item in order["search_activities"]
            if item["long_running"]
        )
        return order
    if (
        order["module"]
        in {
            "pause-unpause",
            "reset",
            "start-delay",
            "update-options",
            "long-running",
        }
        and order["status"] != "delivered"
    ):
        info = await _activity_info(order["activity_id"])
        order["paused"] = info.status == PAUSED_ACTIVITY_STATUS
        order["temporal_attempt"] = info.attempt
        order["temporal_status"] = info.status
        order["activity_started"] = info.HasField("last_started_time")
        order["heartbeat_count"] = info.total_heartbeat_count
        if order["module"] == "long-running":
            heartbeat_confirmed_count = min(
                info.total_heartbeat_count * 2,
                order["batched_confirmation_count"],
            )
            if info.status == COMPLETED_ACTIVITY_STATUS:
                heartbeat_confirmed_count = LONG_RUNNING_CONFIRMATION_TOTAL
            order["heartbeat_confirmed_count"] = heartbeat_confirmed_count
            order["worker_running"] = _worker_pid() is not None
    return order


async def _activity_info(activity_id: str):
    client = await get_temporal_client()
    response = await client.workflow_service.describe_activity_execution(
        DescribeActivityExecutionRequest(
            namespace=client.namespace,
            activity_id=activity_id,
        )
    )
    return response.info


def _worker_pid() -> int | None:
    if not WORKER_PID_PATH.exists():
        return None
    try:
        pid = int(WORKER_PID_PATH.read_text().strip())
        os.kill(pid, 0)
    except (OSError, ValueError):
        WORKER_PID_PATH.unlink(missing_ok=True)
        return None
    return pid


@app.get("/api/worker/status")
async def worker_status() -> dict[str, bool]:
    return {"running": _worker_pid() is not None}


@app.post("/api/worker/kill")
async def kill_worker() -> dict[str, bool]:
    pid = _worker_pid()
    if pid is None:
        raise HTTPException(status_code=409, detail="The Worker is already offline")
    os.kill(pid, signal.SIGKILL)
    for _ in range(30):
        if _worker_pid() is None:
            return {"running": False}
        await asyncio.sleep(0.1)
    raise HTTPException(status_code=504, detail="Timed out stopping the Worker")


@app.post("/api/worker/start")
async def start_worker() -> dict[str, bool]:
    if _worker_pid() is not None:
        raise HTTPException(status_code=409, detail="The Worker is already running")
    WORKER_PID_PATH.unlink(missing_ok=True)
    await asyncio.create_subprocess_exec(
        sys.executable,
        str(RUN_WORKER_PATH),
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(50):
        if _worker_pid() is not None:
            return {"running": True}
        await asyncio.sleep(0.1)
    raise HTTPException(status_code=504, detail="Timed out starting the Worker")


def _pausable_order(order_id: str) -> dict:
    order = store.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["module"] != "pause-unpause":
        raise HTTPException(status_code=409, detail="Order is not using the pause module")
    return order


def _resettable_order(order_id: str) -> dict:
    order = store.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["module"] != "reset":
        raise HTTPException(status_code=409, detail="Order is not using the reset module")
    return order


def _delayed_order(order_id: str) -> dict:
    order = store.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["module"] != "start-delay":
        raise HTTPException(status_code=409, detail="Order is not using start delay")
    return order


def _update_options_order(order_id: str) -> dict:
    order = store.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order["module"] != "update-options":
        raise HTTPException(status_code=409, detail="Order is not using option updates")
    return order


async def _update_retry_maximum_attempts(
    activity_id: str, maximum_attempts: int
) -> None:
    configured_cli = os.getenv("TEMPORAL_CLI_PATH")
    local_prerelease_cli = (
        Path(__file__).resolve().parents[4] / "temporal-cli-prerelease" / "temporal"
    )
    cli = configured_cli or (
        str(local_prerelease_cli) if local_prerelease_cli.exists() else "temporal"
    )
    process = await asyncio.create_subprocess_exec(
        cli,
        "activity",
        "update-options",
        "--activity-id",
        activity_id,
        "--retry-maximum-attempts",
        str(maximum_attempts),
        "--address",
        os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        "--namespace",
        os.getenv("TEMPORAL_NAMESPACE", "default"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode:
        detail = stderr.decode().strip() or "Temporal rejected the option update"
        raise HTTPException(status_code=503, detail=detail)


@app.post("/api/orders/{order_id}/pause")
async def pause_order_activity(order_id: str) -> dict[str, bool]:
    order = _pausable_order(order_id)
    client = await get_temporal_client()
    await client.workflow_service.pause_activity_execution(
        PauseActivityExecutionRequest(
            namespace=client.namespace,
            activity_id=order["activity_id"],
            identity="checkout-demo-operator",
            reason="Pause while downstream bug is repaired",
            request_id=str(uuid.uuid4()),
        )
    )

    # A running attempt is allowed to finish. Wait until Temporal reports the
    # Activity as paused before changing the downstream system.
    for _ in range(50):
        info = await _activity_info(order["activity_id"])
        if info.status == PAUSED_ACTIVITY_STATUS:
            store.fix_downstream_bug(order_id)
            return {"paused": True, "bug_fixed": True}
        await asyncio.sleep(0.1)
    raise HTTPException(status_code=504, detail="Timed out waiting for Activity to pause")


@app.post("/api/orders/{order_id}/unpause")
async def unpause_order_activity(order_id: str) -> dict[str, bool]:
    order = _pausable_order(order_id)
    if not order["bug_fixed"]:
        raise HTTPException(status_code=409, detail="Fix the downstream bug before unpausing")

    client = await get_temporal_client()
    await client.workflow_service.unpause_activity_execution(
        UnpauseActivityExecutionRequest(
            namespace=client.namespace,
            activity_id=order["activity_id"],
            identity="checkout-demo-operator",
            reason="Downstream bug repaired",
            request_id=str(uuid.uuid4()),
        )
    )
    return {"paused": False, "bug_fixed": True}


@app.post("/api/orders/{order_id}/reset")
async def reset_order_activity(order_id: str) -> dict[str, bool]:
    order = _resettable_order(order_id)
    info = await _activity_info(order["activity_id"])
    if info.status != RUNNING_ACTIVITY_STATUS or not order["attempts"]:
        raise HTTPException(
            status_code=409,
            detail="Activity must record a failed attempt before reset",
        )

    # Repair first so the immediately-dispatched reset attempt cannot race the fix.
    store.prepare_reset(order_id, order["activity_id"])
    client = await get_temporal_client()
    await client.workflow_service.reset_activity_execution(
        ResetActivityExecutionRequest(
            namespace=client.namespace,
            activity_id=order["activity_id"],
            identity="checkout-demo-operator",
            request_id=str(uuid.uuid4()),
        )
    )
    return {"reset": True, "bug_fixed": True}


@app.post("/api/orders/{order_id}/cancel")
async def cancel_delayed_activity(order_id: str) -> dict[str, bool]:
    order = _delayed_order(order_id)
    info = await _activity_info(order["activity_id"])
    if info.status != RUNNING_ACTIVITY_STATUS or info.HasField("last_started_time"):
        raise HTTPException(
            status_code=409,
            detail="The Activity has already started and can no longer be canceled here",
        )

    client = await get_temporal_client()
    handle = client.get_activity_handle(order["activity_id"])
    await handle.cancel(reason="Customer canceled before delayed dispatch")
    for _ in range(30):
        info = await _activity_info(order["activity_id"])
        if info.status == CANCELED_ACTIVITY_STATUS:
            store.set_status(order_id, "canceled")
            return {"canceled": True}
        await asyncio.sleep(0.1)
    raise HTTPException(status_code=504, detail="Timed out waiting for cancellation")


@app.post("/api/orders/{order_id}/update-retries")
async def update_activity_retry_options(order_id: str) -> dict[str, int | bool]:
    order = _update_options_order(order_id)
    if order["retry_updated_at"]:
        raise HTTPException(status_code=409, detail="The retry policy was already updated")
    info = await _activity_info(order["activity_id"])
    if info.status != RUNNING_ACTIVITY_STATUS:
        raise HTTPException(
            status_code=409,
            detail="The Activity is no longer running",
        )

    await _update_retry_maximum_attempts(order["activity_id"], 5)
    store.record_retry_option_update(order_id, 5)
    return {
        "updated": True,
        "retry_maximum_attempts": 5,
    }


@app.get("/api/downstream/{order_id}/status")
async def downstream_status(order_id: str) -> dict[str, bool]:
    order = _resettable_order(order_id)
    return {"bug_fixed": order["bug_fixed"]}


@app.post("/api/orders/{order_id}/confirmation-batch")
async def record_confirmation_batch(
    order_id: str, request: ConfirmationBatchRequest
) -> dict[str, int]:
    order = store.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if (
        order["module"] != "long-running"
        or request.activity_id != order["activity_id"]
    ):
        raise HTTPException(status_code=409, detail="Invalid confirmation batch")
    if (
        request.first_confirmation < 1
        or request.last_confirmation > LONG_RUNNING_CONFIRMATION_TOTAL
        or request.last_confirmation != request.first_confirmation
    ):
        raise HTTPException(
            status_code=400,
            detail="Each heartbeat must record one confirmation",
        )
    confirmed_count = store.record_confirmation_batch(
        activity_id=request.activity_id,
        first_confirmation=request.first_confirmation,
        last_confirmation=request.last_confirmation,
    )
    return {"confirmed_count": confirmed_count}


@app.post("/api/webhooks/confirmation")
async def confirmation_webhook(
    webhook: ConfirmationWebhook,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    temporal_attempt: int = Header(1, alias="X-Temporal-Attempt"),
) -> dict[str, bool]:
    if idempotency_key != webhook.activity_id:
        raise HTTPException(status_code=400, detail="Invalid idempotency key")
    order = store.get_order(webhook.order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    if webhook.demo_mode == "retry" and temporal_attempt < 3:
        detail = f"Intermittent failure on attempt {temporal_attempt}"
        store.record_delivery_attempt(
            activity_id=webhook.activity_id,
            attempt=temporal_attempt,
            status="failed",
            detail=detail,
        )
        raise HTTPException(status_code=503, detail=detail)

    if webhook.demo_mode == "pause" and not order["bug_fixed"]:
        detail = f"Downstream system bug on attempt {temporal_attempt}"
        store.record_delivery_attempt(
            activity_id=webhook.activity_id,
            attempt=temporal_attempt,
            status="failed",
            detail=detail,
        )
        raise HTTPException(status_code=503, detail=detail)

    if webhook.demo_mode == "pause":
        await asyncio.sleep(5)

    if webhook.demo_mode == "reset" and not order["bug_fixed"]:
        detail = f"Downstream system bug on attempt {temporal_attempt}"
        store.record_delivery_attempt(
            activity_id=webhook.activity_id,
            attempt=temporal_attempt,
            status="failed",
            detail=detail,
        )
        raise HTTPException(status_code=503, detail=detail)

    if webhook.demo_mode == "update":
        detail = f"Downstream system unavailable on attempt {temporal_attempt}"
        store.record_delivery_attempt(
            activity_id=webhook.activity_id,
            attempt=temporal_attempt,
            status="failed",
            detail=detail,
        )
        raise HTTPException(status_code=503, detail=detail)

    accepted = store.record_confirmation(webhook)
    store.record_delivery_attempt(
        activity_id=webhook.activity_id,
        attempt=temporal_attempt,
        status="delivered",
        detail="Webhook accepted",
    )
    return {"accepted": accepted, "duplicate": not accepted}
