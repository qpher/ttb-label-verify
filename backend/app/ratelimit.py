"""Minimal in-memory rate limiting for a public prototype.

This is deliberately the simplest thing that protects a publicly deployed
demo from drive-by abuse of the model API: a sliding-window counter per
client IP, no external dependencies, no persistence. Production would use
the platform's edge rate limiting or a shared store — documented in README
under "Abuse & cost controls". The primary cost control is the spend limit
set in the Anthropic console; this is the second layer.
"""
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        """Record a hit for `key`; return False if it exceeded the window."""
        now = time.monotonic() if now is None else now
        q = self._hits[key]
        cutoff = now - self.window
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        # Opportunistic cleanup so the map can't grow unbounded on a
        # long-lived public instance.
        if len(self._hits) > 10_000:
            for k in [k for k, v in self._hits.items() if not v]:
                del self._hits[k]
        return True
