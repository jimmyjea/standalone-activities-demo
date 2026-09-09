import asyncio

from checkout_demo.models import SearchAttributeJob
from temporalio import activity


@activity.defn(name="run_search_attribute_activity")
async def run_search_attribute_activity(
    job: SearchAttributeJob,
) -> dict[str, str]:
    if not job.long_running:
        return {"job_id": job.job_id, "status": "completed"}

    for elapsed_seconds in range(600):
        activity.heartbeat(
            {"job_id": job.job_id, "elapsed_seconds": elapsed_seconds}
        )
        await asyncio.sleep(1)
    return {"job_id": job.job_id, "status": "completed"}
