import pytest
import fakeredis
from app.config import settings
from app.services.queue import set_redis_client, reset_redis_client


@pytest.fixture(autouse=True)
def use_fakeredis_for_tests():
    """Autouse fixture that injects FakeRedis instance for automated test execution."""
    fake_client = fakeredis.FakeRedis(decode_responses=False)
    fake_client.delete(settings.REDIS_QUEUE_NAME)
    set_redis_client(fake_client)
    yield fake_client
    fake_client.delete(settings.REDIS_QUEUE_NAME)
    reset_redis_client()
