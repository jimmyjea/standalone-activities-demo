import os
import uuid
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from temporalio.common import RetryPolicy

from .activities import send_order_confirmation
from .models import CheckoutRequest, ConfirmationWebhook, SendConfirmationInput
from .store import DemoStore
from .temporal import TASK_QUEUE, get_temporal_client

MODULE_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = MODULE_ROOT / "static"
ORDER_TOTAL = "$128.00"

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
    activity_id = (
        f"retry-confirmation:{order_id}" if is_retry_demo else f"send-confirmation:{order_id}"
    )
    activity_type = "send_confirmation_with_retries" if is_retry_demo else send_order_confirmation
    webhook_url = os.getenv(
        "CONFIRMATION_WEBHOOK_URL",
        "http://127.0.0.1:8000/api/webhooks/confirmation",
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
        await client.start_activity(
            activity_type,
            args=[
                SendConfirmationInput(
                    activity_id=activity_id,
                    order_id=order_id,
                    customer_name=request.customer_name.strip(),
                    recipient=str(request.email),
                    total=ORDER_TOTAL,
                    webhook_url=webhook_url,
                )
            ],
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
    return order


@app.post("/api/webhooks/confirmation")
async def confirmation_webhook(
    webhook: ConfirmationWebhook,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    temporal_attempt: int = Header(1, alias="X-Temporal-Attempt"),
) -> dict[str, bool]:
    if idempotency_key != webhook.activity_id:
        raise HTTPException(status_code=400, detail="Invalid idempotency key")
    if store.get_order(webhook.order_id) is None:
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

    accepted = store.record_confirmation(webhook)
    store.record_delivery_attempt(
        activity_id=webhook.activity_id,
        attempt=temporal_attempt,
        status="delivered",
        detail="Webhook accepted",
    )
    return {"accepted": accepted, "duplicate": not accepted}
