from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, EmailStr


class CheckoutRequest(BaseModel):
    customer_name: str
    email: EmailStr
    module: Literal[
        "confirmation",
        "webhook-retries",
        "pause-unpause",
        "reset",
        "start-delay",
        "update-options",
        "batch-commands",
        "search-attributes",
        "long-running",
        "fairness",
        "workflow-reuse",
    ] = "confirmation"


class ConfirmationWebhook(BaseModel):
    activity_id: str
    order_id: str
    demo_mode: Literal["standard", "retry", "pause", "reset", "update"]
    recipient: EmailStr
    subject: str
    message: str
    provider_message_id: str


@dataclass
class SendConfirmationInput:
    activity_id: str
    order_id: str
    customer_name: str
    recipient: str
    total: str
    webhook_url: str


@dataclass
class SearchAttributeJob:
    job_id: str
    long_running: bool


@dataclass
class BatchConfirmationInput:
    order_id: str
    activity_id: str
    batch_url: str


class ConfirmationBatchRequest(BaseModel):
    activity_id: str
    first_confirmation: int
    last_confirmation: int


@dataclass
class FairnessConfirmationInput:
    activity_id: str
    merchant: str
    confirmation_number: int
