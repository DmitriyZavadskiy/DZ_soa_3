import asyncio
import logging

import grpc

log = logging.getLogger("retry")

RETRY_CODES = {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED}


class Retry(grpc.aio.UnaryUnaryClientInterceptor):
    def __init__(self, attempts: int, base_ms: int):
        self.attempts = attempts
        self.base_ms = base_ms

    async def intercept_unary_unary(self, continuation, details, request):
        for attempt in range(1, self.attempts + 1):
            call = await continuation(details, request)
            code = await call.code()
            if code not in RETRY_CODES or attempt == self.attempts:
                return call
            delay_ms = self.base_ms * 2 ** (attempt - 1)
            log.warning(
                "%s failed with %s, attempt %s of %s, retry in %s ms",
                details.method.decode(), code.name, attempt, self.attempts, delay_ms,
            )
            await asyncio.sleep(delay_ms / 1000)
