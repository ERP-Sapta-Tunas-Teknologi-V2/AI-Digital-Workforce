import redis
import os

redis_client = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True
)

LOCK_TTL = 3600  # detik, safety net kalau proses crash tanpa release lock

def try_acquire(key: str) -> bool:
    """Return True kalau lock berhasil didapat, False kalau sudah dipegang proses lain."""
    return redis_client.set(f"lock:{key}", "1", nx=True, ex=LOCK_TTL)

def release(key: str):
    redis_client.delete(f"lock:{key}")

def is_locked(key: str) -> bool:
    return redis_client.exists(f"lock:{key}") == 1