"""
AegisAI Rate Limiter Middleware — SlowAPI Integration.

Provides per-endpoint rate limiting using SlowAPI (a FastAPI wrapper around
limits). Different limit buckets are configured for different sensitivity zones:
  - Auth endpoints: strict (20/minute) to prevent brute-force
  - AI endpoints: moderate (20/minute) due to compute cost
  - General endpoints: relaxed (100/minute)

The limiter uses the client's IP address as the key by default.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config.settings import settings

# ---------------------------------------------------------------------------
# Global Limiter — import this instance in router files
# ---------------------------------------------------------------------------
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri="memory://" if settings.ENVIRONMENT in ("test", "testing", "development") else settings.REDIS_URL,
    strategy="fixed-window",
)
