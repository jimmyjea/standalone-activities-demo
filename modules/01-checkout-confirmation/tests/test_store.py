from checkout_demo.models import ConfirmationWebhook
from checkout_demo.store import DemoStore


def test_confirmation_webhook_is_idempotent(tmp_path):
    store = DemoStore(tmp_path / "test.db")
    store.create_order(
        order_id="DEMO-123",
        customer_name="Jordan Lee",
        email="jordan@example.com",
        total="$128.00",
        activity_id="send-confirmation:DEMO-123",
    )
    webhook = ConfirmationWebhook(
        activity_id="send-confirmation:DEMO-123",
        order_id="DEMO-123",
        demo_mode="standard",
        recipient="jordan@example.com",
        subject="Order confirmed",
        message="Your order is confirmed.",
        provider_message_id="msg_123",
    )

    assert store.record_confirmation(webhook) is True
    assert store.record_confirmation(webhook) is False

    order = store.get_order("DEMO-123")
    assert order is not None
    assert order["status"] == "delivered"
    assert order["provider_message_id"] == "msg_123"


def test_delivery_attempts_are_returned_in_order(tmp_path):
    store = DemoStore(tmp_path / "test.db")
    store.create_order(
        order_id="DEMO-RETRY",
        customer_name="Jordan Lee",
        email="jordan@example.com",
        total="$128.00",
        activity_id="retry-confirmation:DEMO-RETRY",
    )
    store.record_delivery_attempt(
        activity_id="retry-confirmation:DEMO-RETRY",
        attempt=2,
        status="failed",
        detail="Intermittent failure on attempt 2",
    )
    store.record_delivery_attempt(
        activity_id="retry-confirmation:DEMO-RETRY",
        attempt=1,
        status="failed",
        detail="Intermittent failure on attempt 1",
    )

    order = store.get_order("DEMO-RETRY")
    assert order is not None
    assert order["module"] == "webhook-retries"
    assert [attempt["attempt"] for attempt in order["attempts"]] == [1, 2]
