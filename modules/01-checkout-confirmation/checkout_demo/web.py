import asyncio
import os
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
from temporalio.common import RetryPolicy

from .activities import send_order_confirmation
from .models import CheckoutRequest, ConfirmationWebhook, SendConfirmationInput
from .store import DemoStore
from .temporal import TASK_QUEUE, get_temporal_client

MODULE_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = MODULE_ROOT / "static"
ORDER_TOTAL = "$128.00"
# The prerelease Server returns PAUSED before the stable SDK names this enum value.
PAUSED_ACTIVITY_STATUS = 7
FAILED_ACTIVITY_STATUS = 3
RUNNING_ACTIVITY_STATUS = 1
CANCELED_ACTIVITY_STATUS = 4

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
    if is_pause_demo:
        activity_id = f"pausable-confirmation:{order_id}"
    elif is_reset_demo:
        activity_id = f"reset-confirmation:{order_id}"
    elif is_start_delay_demo:
        activity_id = f"delayed-confirmation:{order_id}"
    elif is_update_options_demo:
        activity_id = f"updated-delay-confirmation:{order_id}"
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
        if is_pause_demo:
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
                start_delay=timedelta(seconds=10),
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
                start_delay=timedelta(seconds=10),
                schedule_to_close_timeout=timedelta(minutes=1),
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(maximum_attempts=3),
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
    if (
        order["module"]
        in {"pause-unpause", "reset", "start-delay", "update-options"}
        and order["status"] != "delivered"
    ):
        info = await _activity_info(order["activity_id"])
        order["paused"] = info.status == PAUSED_ACTIVITY_STATUS
        order["temporal_attempt"] = info.attempt
        order["temporal_status"] = info.status
        order["activity_started"] = info.HasField("last_started_time")
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


async def _update_start_delay(activity_id: str, seconds: int) -> None:
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
        "--start-delay",
        f"{seconds}s",
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


@app.post("/api/orders/{order_id}/update-delay")
async def update_activity_start_delay(order_id: str) -> dict[str, int | bool]:
    order = _update_options_order(order_id)
    if order["delay_updated_at"]:
        raise HTTPException(status_code=409, detail="The start delay was already updated")
    info = await _activity_info(order["activity_id"])
    if info.status != RUNNING_ACTIVITY_STATUS or info.HasField("last_started_time"):
        raise HTTPException(
            status_code=409,
            detail="The Activity has already started and its delay cannot be updated",
        )

    await _update_start_delay(order["activity_id"], 5)
    store.record_start_delay_update(order_id, 5)
    return {"updated": True, "start_delay_seconds": 5}


@app.get("/api/downstream/{order_id}/status")
async def downstream_status(order_id: str) -> dict[str, bool]:
    order = _resettable_order(order_id)
    return {"bug_fixed": order["bug_fixed"]}


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

    if webhook.demo_mode == "reset" and not order["bug_fixed"]:
        detail = f"Downstream system bug on attempt {temporal_attempt}"
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
