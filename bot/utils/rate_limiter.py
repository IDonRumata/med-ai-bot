"""Simple in-memory rate limiter to protect OpenAI API budget."""
import time
from collections import deque


class RateLimiter:
    def __init__(self, max_calls: int, period_seconds: int):
        self._max_calls = max_calls
        self._period = period_seconds
        self._calls: deque[float] = deque()

    def is_allowed(self) -> bool:
        now = time.monotonic()
        # Remove calls outside the window
        while self._calls and now - self._calls[0] > self._period:
            self._calls.popleft()
        if len(self._calls) >= self._max_calls:
            return False
        self._calls.append(now)
        return True

    def seconds_until_reset(self) -> int:
        if not self._calls:
            return 0
        oldest = self._calls[0]
        return max(0, int(self._period - (time.monotonic() - oldest)))


# Global limiter: max 20 AI calls per hour (personal bot, ~$0.50/hour max)
ai_limiter = RateLimiter(max_calls=20, period_seconds=3600)
