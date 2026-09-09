import asyncio

from temporalio import activity


@activity.defn(name="run_long_running_batch_activity")
async def run_long_running_batch_activity(job_id: str) -> dict[str, str]:
    """Represent long-running work and heartbeat for cooperative cancellation."""
    activity.logger.info("Starting long-running batch job %s", job_id)
    for elapsed_seconds in range(600):
        activity.heartbeat({"job_id": job_id, "elapsed_seconds": elapsed_seconds})
        await asyncio.sleep(1)
    return {"job_id": job_id, "status": "completed"}
