import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ConfirmationWebhook

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "demo.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DemoStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or os.getenv("DEMO_DB_PATH", DEFAULT_DB_PATH))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    customer_name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    total TEXT NOT NULL,
                    status TEXT NOT NULL,
                    activity_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    delivered_at TEXT,
                    subject TEXT,
                    message TEXT,
                    provider_message_id TEXT,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS webhook_receipts (
                    activity_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    received_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS webhook_attempts (
                    activity_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    attempted_at TEXT NOT NULL,
                    PRIMARY KEY (activity_id, attempt)
                );

                CREATE TABLE IF NOT EXISTS operator_state (
                    order_id TEXT PRIMARY KEY,
                    bug_fixed INTEGER NOT NULL DEFAULT 0,
                    fixed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS operator_resets (
                    order_id TEXT PRIMARY KEY,
                    reset_at TEXT NOT NULL,
                    previous_attempts TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS retry_option_updates (
                    order_id TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    maximum_attempts INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS batched_confirmations (
                    activity_id TEXT NOT NULL,
                    confirmation_number INTEGER NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (activity_id, confirmation_number)
                );
                """
            )

    def create_order(
        self,
        *,
        order_id: str,
        customer_name: str,
        email: str,
        total: str,
        activity_id: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO orders (
                    id, customer_name, email, total, status, activity_id, created_at
                ) VALUES (?, ?, ?, ?, 'scheduling', ?, ?)
                """,
                (order_id, customer_name, email, total, activity_id, _now()),
            )
            connection.execute(
                "INSERT INTO operator_state (order_id) VALUES (?)",
                (order_id,),
            )

    def set_status(self, order_id: str, status: str, error: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE orders
                SET status = ?, error = ?
                WHERE id = ? AND status != 'delivered'
                """,
                (status, error, order_id),
            )

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if row is None:
                return None
            attempts = connection.execute(
                """
                SELECT attempt, status, detail, attempted_at
                FROM webhook_attempts
                WHERE activity_id = ?
                ORDER BY attempt
                """,
                (row["activity_id"],),
            ).fetchall()
            operator_state = connection.execute(
                "SELECT bug_fixed, fixed_at FROM operator_state WHERE order_id = ?",
                (order_id,),
            ).fetchone()
            reset = connection.execute(
                """
                SELECT reset_at, previous_attempts
                FROM operator_resets
                WHERE order_id = ?
                """,
                (order_id,),
            ).fetchone()
            retry_update = connection.execute(
                """
                SELECT updated_at, maximum_attempts
                FROM retry_option_updates
                WHERE order_id = ?
                """,
                (order_id,),
            ).fetchone()
            batched_confirmation_count = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM batched_confirmations
                WHERE activity_id = ?
                """,
                (row["activity_id"],),
            ).fetchone()["count"]
            batched_confirmations = connection.execute(
                """
                SELECT confirmation_number, recorded_at
                FROM batched_confirmations
                WHERE activity_id = ?
                ORDER BY confirmation_number
                """,
                (row["activity_id"],),
            ).fetchall()

        order = dict(row)
        if order["activity_id"].startswith("retry-confirmation:"):
            order["module"] = "webhook-retries"
        elif order["activity_id"].startswith("pausable-confirmation:"):
            order["module"] = "pause-unpause"
        elif order["activity_id"].startswith("reset-confirmation:"):
            order["module"] = "reset"
        elif order["activity_id"].startswith("delayed-confirmation:"):
            order["module"] = "start-delay"
        elif order["activity_id"].startswith("options-confirmation:"):
            order["module"] = "update-options"
        elif order["activity_id"].startswith("batch-group:"):
            order["module"] = "batch-commands"
        elif order["activity_id"].startswith("search-group:"):
            order["module"] = "search-attributes"
        elif order["activity_id"].startswith("batched-confirmations:"):
            order["module"] = "long-running"
        elif order["activity_id"].startswith("fairness-group:"):
            order["module"] = "fairness"
        elif order["activity_id"].startswith("fulfillment-workflow:"):
            order["module"] = "workflow-reuse"
        else:
            order["module"] = "confirmation"
        order["attempts"] = [dict(attempt) for attempt in attempts]
        order["bug_fixed"] = bool(operator_state["bug_fixed"]) if operator_state else False
        order["fixed_at"] = operator_state["fixed_at"] if operator_state else None
        order["reset_at"] = reset["reset_at"] if reset else None
        order["previous_attempts"] = json.loads(reset["previous_attempts"]) if reset else []
        order["retry_updated_at"] = (
            retry_update["updated_at"] if retry_update else None
        )
        order["retry_maximum_attempts"] = (
            retry_update["maximum_attempts"] if retry_update else 20
        )
        order["start_delay_seconds"] = 60
        order["batched_confirmation_count"] = batched_confirmation_count
        order["batched_confirmations"] = [
            dict(confirmation) for confirmation in batched_confirmations
        ]
        return order

    def record_confirmation_batch(
        self,
        *,
        activity_id: str,
        first_confirmation: int,
        last_confirmation: int,
    ) -> int:
        with self._connect() as connection:
            for confirmation_number in range(
                first_confirmation, last_confirmation + 1
            ):
                connection.execute(
                    """
                    INSERT OR IGNORE INTO batched_confirmations (
                        activity_id, confirmation_number, recorded_at
                    ) VALUES (?, ?, ?)
                    """,
                    (activity_id, confirmation_number, _now()),
                )
            return connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM batched_confirmations
                WHERE activity_id = ?
                """,
                (activity_id,),
            ).fetchone()["count"]

    def record_retry_option_update(
        self, order_id: str, maximum_attempts: int
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO retry_option_updates (
                    order_id, updated_at, maximum_attempts
                ) VALUES (?, ?, ?)
                """,
                (order_id, _now(), maximum_attempts),
            )

    def fix_downstream_bug(self, order_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE operator_state
                SET bug_fixed = 1, fixed_at = ?
                WHERE order_id = ?
                """,
                (_now(), order_id),
            )

    def prepare_reset(self, order_id: str, activity_id: str) -> None:
        with self._connect() as connection:
            attempts = connection.execute(
                """
                SELECT attempt, status, detail, attempted_at
                FROM webhook_attempts
                WHERE activity_id = ?
                ORDER BY attempt
                """,
                (activity_id,),
            ).fetchall()
            connection.execute(
                """
                INSERT OR IGNORE INTO operator_resets (
                    order_id, reset_at, previous_attempts
                ) VALUES (?, ?, ?)
                """,
                (
                    order_id,
                    _now(),
                    json.dumps([dict(attempt) for attempt in attempts]),
                ),
            )
            connection.execute(
                "DELETE FROM webhook_attempts WHERE activity_id = ?",
                (activity_id,),
            )
            connection.execute(
                """
                UPDATE operator_state
                SET bug_fixed = 1, fixed_at = ?
                WHERE order_id = ?
                """,
                (_now(), order_id),
            )

    def record_delivery_attempt(
        self,
        *,
        activity_id: str,
        attempt: int,
        status: str,
        detail: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO webhook_attempts (
                    activity_id, attempt, status, detail, attempted_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (activity_id, attempt, status, detail, _now()),
            )

    def record_confirmation(self, webhook: ConfirmationWebhook) -> bool:
        received_at = _now()
        payload = json.dumps(webhook.model_dump(mode="json"), sort_keys=True)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO webhook_receipts (
                    activity_id, order_id, payload, received_at
                ) VALUES (?, ?, ?, ?)
                """,
                (webhook.activity_id, webhook.order_id, payload, received_at),
            )
            inserted = cursor.rowcount == 1
            if inserted:
                connection.execute(
                    """
                    UPDATE orders
                    SET status = 'delivered',
                        delivered_at = ?,
                        subject = ?,
                        message = ?,
                        provider_message_id = ?,
                        error = NULL
                    WHERE id = ? AND activity_id = ?
                    """,
                    (
                        received_at,
                        webhook.subject,
                        webhook.message,
                        webhook.provider_message_id,
                        webhook.order_id,
                        webhook.activity_id,
                    ),
                )
        return inserted
