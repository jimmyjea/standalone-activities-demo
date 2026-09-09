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

        order = dict(row)
        order["module"] = (
            "webhook-retries"
            if order["activity_id"].startswith("retry-confirmation:")
            else "confirmation"
        )
        order["attempts"] = [dict(attempt) for attempt in attempts]
        return order

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
