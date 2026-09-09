import asyncio

from temporalio import activity


@activity.defn
async def check_inventory(order_id: str) -> dict[str, str]:
    await asyncio.sleep(1)
    return {"order_id": order_id, "status": "in_stock"}


@activity.defn
async def process_payment(order_id: str) -> dict[str, str]:
    await asyncio.sleep(1)
    return {"order_id": order_id, "status": "authorized"}


@activity.defn
async def prepare_shipment(order_id: str) -> dict[str, str]:
    await asyncio.sleep(1)
    return {"order_id": order_id, "status": "prepared"}
