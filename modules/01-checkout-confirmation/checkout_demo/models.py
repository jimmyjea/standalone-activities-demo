from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, EmailStr


class CheckoutRequest(BaseModel):
    customer_name: str
    email: EmailStr
    module: Literal["confirmation", "webhook-retries"] = "confirmation"


class ConfirmationWebhook(BaseModel):
    activity_id: str
    order_id: str
    demo_mode: Literal["standard", "retry"]
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
