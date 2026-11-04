import logging
import time

import grpc

log = logging.getLogger("breaker")

FAILURE_CODES = {
    grpc.StatusCode.UNAVAILABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED,
    grpc.StatusCode.INTERNAL,
    grpc.StatusCode.UNKNOWN,
}


class BreakerOpen(Exception):
    pass


class Breaker(grpc.aio.UnaryUnaryClientInterceptor):
    def __init__(self, max_failures: int, window_seconds: float, open_seconds: float):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.open_seconds = open_seconds
        self.state = "CLOSED"
        self.failures: list[float] = []
        self.opened_at = 0.0
        self.trial = False

    def set_state(self, new_state: str) -> None:
        log.warning("circuit breaker %s -> %s", self.state, new_state)
        self.state = new_state

    def on_failure(self) -> None:
        now = time.monotonic()
        if self.state == "HALF_OPEN":
            self.opened_at = now
            self.set_state("OPEN")
            return
        self.failures = [t for t in self.failures if now - t < self.window_seconds]
        self.failures.append(now)
        if self.state == "CLOSED" and len(self.failures) >= self.max_failures:
            self.opened_at = now
            self.set_state("OPEN")

    def on_success(self) -> None:
        self.failures = []
        if self.state == "HALF_OPEN":
            self.set_state("CLOSED")

    async def intercept_unary_unary(self, continuation, details, request):
        if self.state == "OPEN":
            if time.monotonic() - self.opened_at < self.open_seconds:
                raise BreakerOpen("flight service is unavailable, circuit breaker is open")
            self.set_state("HALF_OPEN")

        if self.state == "HALF_OPEN":
            if self.trial:
                raise BreakerOpen("flight service is unavailable, circuit breaker is half open")
            self.trial = True

        try:
            call = await continuation(details, request)
            code = await call.code()
        except Exception:
            self.on_failure()
            raise
        finally:
            self.trial = False

        if code in FAILURE_CODES:
            self.on_failure()
        else:
            self.on_success()
        return call
