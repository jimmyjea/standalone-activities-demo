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


def test_operator_can_fix_downstream_bug(tmp_path):
    store = DemoStore(tmp_path / "test.db")
    store.create_order(
        order_id="DEMO-PAUSE",
        customer_name="Jordan Lee",
        email="jordan@example.com",
        total="$128.00",
        activity_id="pausable-confirmation:DEMO-PAUSE",
    )

    before = store.get_order("DEMO-PAUSE")
    assert before is not None
    assert before["module"] == "pause-unpause"
    assert before["bug_fixed"] is False

    store.fix_downstream_bug("DEMO-PAUSE")

    after = store.get_order("DEMO-PAUSE")
    assert after is not None
    assert after["bug_fixed"] is True
    assert after["fixed_at"] is not None


def test_prepare_reset_records_operator_action_and_fixes_bug(tmp_path):
    store = DemoStore(tmp_path / "test.db")
    activity_id = "reset-confirmation:DEMO-RESET"
    store.create_order(
        order_id="DEMO-RESET",
        customer_name="Jordan Lee",
        email="jordan@example.com",
        total="$128.00",
        activity_id=activity_id,
    )
    for attempt in range(1, 3):
        store.record_delivery_attempt(
            activity_id=activity_id,
            attempt=attempt,
            status="failed",
            detail=f"Downstream system bug on attempt {attempt}",
        )
    store.prepare_reset("DEMO-RESET", activity_id)

    order = store.get_order("DEMO-RESET")
    assert order is not None
    assert order["module"] == "reset"
    assert order["bug_fixed"] is True
    assert order["attempts"] == []
    assert [attempt["attempt"] for attempt in order["previous_attempts"]] == [1, 2]
    assert order["reset_at"] is not None


def test_delayed_activity_id_selects_start_delay_module(tmp_path):
    store = DemoStore(tmp_path / "test.db")
    store.create_order(
        order_id="DEMO-DELAY",
        customer_name="Jordan Lee",
        email="jordan@example.com",
        total="$128.00",
        activity_id="delayed-confirmation:DEMO-DELAY",
    )

    order = store.get_order("DEMO-DELAY")
    assert order is not None
    assert order["module"] == "start-delay"


def test_retry_option_update_is_returned_with_order(tmp_path):
    store = DemoStore(tmp_path / "test.db")
    store.create_order(
        order_id="DEMO-UPDATE",
        customer_name="Jordan Lee",
        email="jordan@example.com",
        total="$128.00",
        activity_id="options-confirmation:DEMO-UPDATE",
    )

    before = store.get_order("DEMO-UPDATE")
    assert before is not None
    assert before["module"] == "update-options"
    assert before["retry_maximum_attempts"] == 20
    assert before["retry_updated_at"] is None

    store.record_retry_option_update("DEMO-UPDATE", 5)

    after = store.get_order("DEMO-UPDATE")
    assert after is not None
    assert after["retry_maximum_attempts"] == 5
    assert after["retry_updated_at"] is not None


def test_batch_group_id_selects_batch_commands_module(tmp_path):
    store = DemoStore(tmp_path / "test.db")
    store.create_order(
        order_id="DEMO-BATCH",
        customer_name="Jordan Lee",
        email="jordan@example.com",
        total="$128.00",
        activity_id="batch-group:DEMO-BATCH",
    )

    order = store.get_order("DEMO-BATCH")
    assert order is not None
    assert order["module"] == "batch-commands"


def test_search_group_id_selects_search_attributes_module(tmp_path):
    store = DemoStore(tmp_path / "test.db")
    store.create_order(
        order_id="DEMO-SEARCH",
        customer_name="Jordan Lee",
        email="jordan@example.com",
        total="$128.00",
        activity_id="search-group:DEMO-SEARCH",
    )

    order = store.get_order("DEMO-SEARCH")
    assert order is not None
    assert order["module"] == "search-attributes"


def test_batched_confirmation_progress_is_idempotent(tmp_path):
    store = DemoStore(tmp_path / "test.db")
    activity_id = "batched-confirmations:DEMO-BATCHED"
    store.create_order(
        order_id="DEMO-BATCHED",
        customer_name="Jordan Lee",
        email="jordan@example.com",
        total="$128.00",
        activity_id=activity_id,
    )
    store.record_confirmation_batch(
        activity_id=activity_id,
        first_confirmation=1,
        last_confirmation=2,
    )
    store.record_confirmation_batch(
        activity_id=activity_id,
        first_confirmation=1,
        last_confirmation=2,
    )

    order = store.get_order("DEMO-BATCHED")
    assert order is not None
    assert order["module"] == "long-running"
    assert order["batched_confirmation_count"] == 2
    assert [
        confirmation["confirmation_number"]
        for confirmation in order["batched_confirmations"]
    ] == [1, 2]


def test_fairness_group_id_selects_fairness_module(tmp_path):
    store = DemoStore(tmp_path / "test.db")
    store.create_order(
        order_id="DEMO-FAIR",
        customer_name="Jordan Lee",
        email="jordan@example.com",
        total="$128.00",
        activity_id="fairness-group:DEMO-FAIR",
    )

    order = store.get_order("DEMO-FAIR")
    assert order is not None
    assert order["module"] == "fairness"


def test_fulfillment_workflow_id_selects_reuse_module(tmp_path):
    store = DemoStore(tmp_path / "test.db")
    store.create_order(
        order_id="DEMO-WORKFLOW",
        customer_name="Jordan Lee",
        email="jordan@example.com",
        total="$128.00",
        activity_id="fulfillment-workflow:DEMO-WORKFLOW",
    )

    order = store.get_order("DEMO-WORKFLOW")
    assert order is not None
    assert order["module"] == "workflow-reuse"
