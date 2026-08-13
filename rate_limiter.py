"""
rate_limiter.py — Product Analytics Groq RPM Rate Limiter

Implements a sliding-window rate limiter to enforce Groq's free-tier limit of
30 requests per minute (RPM) across ALL LLM calls globally (light + heavy models).

Usage:
    from rate_limiter import groq_rate_limiter

    # Before every groq_client.chat.completions.create() call:
    groq_rate_limiter.wait()

How it works:
    - Maintains a deque of timestamps for the last N requests.
    - Before each call, evicts timestamps older than 60 seconds.
    - If the window already has MAX_RPM entries, sleeps until the oldest
      entry is more than 60 seconds old (i.e., slides out of the window).
    - Thread-safe via threading.Lock.

Limits (Groq free tier as of April 2026):
    Light model  (llama3-8b-8192):            30 RPM / 14,400 RPD
    Heavy model  (llama-3.3-70b-versatile):   30 RPM /  1,000 RPD
"""

import time
import threading
from collections import deque


class SlidingWindowRateLimiter:
    """
    A thread-safe sliding-window rate limiter.

    Args:
        max_requests: Maximum number of requests allowed in the window.
        window_seconds: Duration of the sliding window in seconds.
        min_gap_seconds: Minimum guaranteed gap between consecutive calls.
                         Acts as a floor even when well under the RPM cap.
    """

    def __init__(
        self,
        max_requests: int = 30,
        window_seconds: float = 60.0,
        min_gap_seconds: float = 2.5,
    ) -> None:
        self._max_requests = max_requests
        self._window = window_seconds
        self._min_gap = min_gap_seconds
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def wait(self) -> None:
        """
        Block until a Groq API call is safe to issue.

        Enforces two constraints:
          1. No more than max_requests calls in the trailing window_seconds.
          2. At least min_gap_seconds since the last call (burst prevention).
        """
        with self._lock:
            now = time.monotonic()

            # ── Constraint 1: Sliding-window RPM cap ─────────────────────────
            # Evict timestamps that have slipped outside the window
            while self._timestamps and (now - self._timestamps[0]) >= self._window:
                self._timestamps.popleft()

            if len(self._timestamps) >= self._max_requests:
                # Must wait until the oldest timestamp is outside the window
                oldest = self._timestamps[0]
                sleep_needed = self._window - (now - oldest) + 0.1  # +100ms buffer
                if sleep_needed > 0:
                    print(
                        f"[rate_limiter] ⏳ RPM cap reached ({self._max_requests}/min). "
                        f"Sleeping {sleep_needed:.1f}s..."
                    )
                    time.sleep(sleep_needed)
                    now = time.monotonic()
                    # Re-evict after sleep
                    while self._timestamps and (now - self._timestamps[0]) >= self._window:
                        self._timestamps.popleft()

            # ── Constraint 2: Minimum inter-call gap ─────────────────────────
            if self._timestamps:
                last_call = self._timestamps[-1]
                gap = now - last_call
                if gap < self._min_gap:
                    time.sleep(self._min_gap - gap)
                    now = time.monotonic()

            # Record this call
            self._timestamps.append(time.monotonic())

    def status(self) -> dict:
        """Return current limiter state for debugging/logging."""
        with self._lock:
            now = time.monotonic()
            active = sum(1 for t in self._timestamps if (now - t) < self._window)
            return {
                "requests_in_window": active,
                "max_rpm": self._max_requests,
                "window_seconds": self._window,
                "min_gap_seconds": self._min_gap,
            }


# ─── Global Singleton ─────────────────────────────────────────────────────────
# Shared across aso_router.py and json_synthesizer.py to enforce the 30 RPM
# ceiling across ALL Groq calls, regardless of which module issues them.

groq_rate_limiter = SlidingWindowRateLimiter(
    max_requests=28,      # Use 28 of 30 — leave 2 slots as safety buffer
    window_seconds=60.0,
    min_gap_seconds=2.5,  # 2.5s floor between calls (~24 RPM sustained max)
)
