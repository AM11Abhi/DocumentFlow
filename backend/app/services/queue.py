import json
import logging
import uuid
from typing import Optional, Tuple
import redis
from app.config import settings

logger = logging.getLogger(__name__)

# Cached active client instance
_redis_client_instance: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Returns an active Redis client connection.

    Redis is a required runtime dependency for the application.
    """
    global _redis_client_instance
    if _redis_client_instance is not None:
        return _redis_client_instance

    _redis_client_instance = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=False,
    )
    return _redis_client_instance


def set_redis_client(client: Optional[redis.Redis]):
    """Overrides the Redis client instance (used for testing/mocking)."""
    global _redis_client_instance
    _redis_client_instance = client


def reset_redis_client():
    """Resets the cached Redis client instance."""
    global _redis_client_instance
    _redis_client_instance = None


def enqueue_job(job_id: uuid.UUID, document_id: uuid.UUID) -> bool:
    """Pushes a minimal job payload to the Redis processing queue."""
    client = get_redis_client()
    payload = json.dumps({"job_id": str(job_id), "document_id": str(document_id)})
    client.rpush(settings.REDIS_QUEUE_NAME, payload)
    return True


def dequeue_job(timeout: int = 2) -> Optional[Tuple[uuid.UUID, uuid.UUID]]:
    """Pops the next job payload from the Redis queue.

    Returns (job_id, document_id) or None if timeout expires.
    """
    client = get_redis_client()
    try:
        result = client.blpop(settings.REDIS_QUEUE_NAME, timeout=timeout)
        if not result:
            return None
        _, raw_payload = result
        data = json.loads(raw_payload.decode("utf-8"))
        return uuid.UUID(data["job_id"]), uuid.UUID(data["document_id"])
    except Exception as exc:
        logger.error(f"Error popping job from Redis queue: {exc}")
        return None
