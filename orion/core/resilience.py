import asyncio
import logging
from enum import Enum
from orion.core.config import (
    CIRCUIT_BREAKER_LLM_THRESHOLD,
    CIRCUIT_BREAKER_LLM_WINDOW_SECONDS,
    CIRCUIT_BREAKER_MCP_THRESHOLD,
    CIRCUIT_BREAKER_MCP_WINDOW_SECONDS,
    RETRY_BACKOFF_SEQUENCE,
    RETRY_MAX_ATTEMPTS,
)

logger = logging.getLogger(__name__)

class CircuitState(str, Enum):
    CLOSED = "closed"    # normal — calls go through
    OPEN = "open"        # failing — calls blocked
    HALF_OPEN = "half_open"  # testing — one call allowed

class CircuitOpenError(Exception):
    pass

class CircuitBreaker:
    """
    Tracks failures in a sliding window.
    Opens circuit after threshold failures in window_seconds.
    Resets after window_seconds with no new failures.
    Thread-safe via asyncio.Lock.
    """
    def __init__(self, name: str, threshold: int, window_seconds: int):
        self.name = name
        self.threshold = threshold
        self.window_seconds = window_seconds
        self._failures: list[float] = []  # timestamps
        self._state = CircuitState.CLOSED
        self._lock = asyncio.Lock()

    async def call(self, coro):
        """
        Wraps a coroutine with circuit breaker logic.
        If OPEN: raise CircuitOpenError immediately without calling coro.
        If CLOSED or HALF_OPEN: call coro.
            On success: record success, move to CLOSED.
            On failure: record failure, check threshold, maybe move to OPEN.
        """
        async with self._lock:
            self._cleanup_old_failures()
            if self._state == CircuitState.OPEN:
                raise CircuitOpenError(f"Circuit {self.name} is OPEN")

        try:
            result = await coro
            async with self._lock:
                self._state = CircuitState.CLOSED
            return result
        except Exception as e:
            async with self._lock:
                self._failures.append(asyncio.get_event_loop().time())
                if len(self._failures) >= self.threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(f"Circuit {self.name} OPENED after {self.threshold} failures")
            raise

    def _cleanup_old_failures(self):
        now = asyncio.get_event_loop().time()
        self._failures = [
            t for t in self._failures
            if now - t < self.window_seconds
        ]
        if self._state == CircuitState.OPEN and not self._failures:
            self._state = CircuitState.HALF_OPEN
            logger.info(f"Circuit {self.name} moved to HALF_OPEN")

    @property
    def state(self) -> CircuitState:
        return self._state

async def retry_with_backoff(coro_fn, *args, **kwargs):
    """
    Retries coro_fn(*args, **kwargs) with exponential backoff.
    Uses RETRY_BACKOFF_SEQUENCE = [1, 2, 4, 8, 16] seconds.
    Max attempts = RETRY_MAX_ATTEMPTS = 5.
    Does NOT retry on CircuitOpenError — re-raises immediately.
    Logs each retry attempt with attempt number and wait time.
    On final failure: re-raises the last exception.
    """
    last_error = None
    for attempt, wait in enumerate(RETRY_BACKOFF_SEQUENCE[:RETRY_MAX_ATTEMPTS], 1):
        try:
            return await coro_fn(*args, **kwargs)
        except CircuitOpenError:
            raise
        except Exception as e:
            last_error = e
            if attempt < RETRY_MAX_ATTEMPTS:
                logger.warning(f"Retry {attempt}/{RETRY_MAX_ATTEMPTS} after {wait}s: {e}")
                await asyncio.sleep(wait)
    raise last_error

# Singletons — one circuit per service
llm_circuit = CircuitBreaker(
    "llm",
    CIRCUIT_BREAKER_LLM_THRESHOLD,
    CIRCUIT_BREAKER_LLM_WINDOW_SECONDS
)

mcp_circuit = CircuitBreaker(
    "mcp",
    CIRCUIT_BREAKER_MCP_THRESHOLD,
    CIRCUIT_BREAKER_MCP_WINDOW_SECONDS
)
