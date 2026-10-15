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


@pytest.fixture(autouse=True)
def clean_outbox_for_tests():
    """Ensures no pending outbox events leak between tests."""
    from app.db.session import SessionLocal
    from app.models.outbox import OutboxEvent, OutboxStatus
    db = SessionLocal()
    try:
        db.query(OutboxEvent).filter(OutboxEvent.status == OutboxStatus.PENDING).update(
            {"status": OutboxStatus.PUBLISHED}, synchronize_session=False
        )
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(OutboxEvent).filter(OutboxEvent.status == OutboxStatus.PENDING).update(
            {"status": OutboxStatus.PUBLISHED}, synchronize_session=False
        )
        db.commit()
    finally:
        db.close()

