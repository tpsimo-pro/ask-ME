class RateLimiter:
    """Simple rate limiter for testing."""

    def __init__(self):
        self._hits = {}

    def reset(self):
        """Reset the hits counter."""
        self._hits.clear()


analyze_rate_limiter = RateLimiter()
