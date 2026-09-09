from temporalio.client import Client
from temporalio.envconfig import ClientConfig

TASK_QUEUE = "checkout-confirmations"

_client: Client | None = None


async def get_temporal_client() -> Client:
    global _client
    if _client is None:
        connect_config = ClientConfig.load_client_connect_config()
        connect_config.setdefault("target_host", "localhost:7233")
        _client = await Client.connect(**connect_config)
    return _client
