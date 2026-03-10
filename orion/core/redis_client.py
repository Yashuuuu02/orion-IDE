import logging
from redis.asyncio import Redis, ConnectionError
from orion.core.config import settings

logger = logging.getLogger(__name__)

redis_client = None

async def init_redis():
    global redis_client
    if settings.REDIS_URL:
        if settings.REDIS_URL == "redis://dummy" or settings.REDIS_URL == "test":
            logger.warning("Dummy REDIS_URL detected, skipping actual connection")
            return

        redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            await redis_client.ping()
            logger.info("Connected to Redis")
        except ConnectionError as e:
            logger.error(f"Failed to connect to Redis at {settings.REDIS_URL}")
            raise RuntimeError(f"Redis connection error: {e}")
    else:
        logger.warning("REDIS_URL not set. Redis client will not be initialized.")

def get_redis() -> Redis:
    if redis_client is None:
        raise RuntimeError("Redis client not initialized.")
    return redis_client

async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()
