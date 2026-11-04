import logging
import os
from contextlib import asynccontextmanager

import asyncpg
import grpc
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from breaker import Breaker, BreakerOpen
from client import FlightClient
from handlers import router
from retry import Retry

HTTP_STATUS = {
    grpc.StatusCode.INVALID_ARGUMENT: 400,
    grpc.StatusCode.NOT_FOUND: 404,
    grpc.StatusCode.FAILED_PRECONDITION: 409,
    grpc.StatusCode.RESOURCE_EXHAUSTED: 409,
    grpc.StatusCode.UNAVAILABLE: 503,
    grpc.StatusCode.DEADLINE_EXCEEDED: 504,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app.state.db = await asyncpg.create_pool(os.environ["DATABASE_URL"])
    app.state.flight = FlightClient(
        os.environ["FLIGHT_ADDRESS"],
        os.environ["API_KEY"],
        float(os.environ["TIMEOUT_SECONDS"]),
        interceptors=[
            Breaker(
                int(os.environ["BREAKER_FAILURES"]),
                float(os.environ["BREAKER_WINDOW_SECONDS"]),
                float(os.environ["BREAKER_OPEN_SECONDS"]),
            ),
            Retry(int(os.environ["RETRY_ATTEMPTS"]), int(os.environ["RETRY_BASE_MS"])),
        ],
    )
    yield
    await app.state.flight.close()
    await app.state.db.close()


app = FastAPI(lifespan=lifespan)
app.include_router(router)


@app.exception_handler(grpc.aio.AioRpcError)
async def grpc_error(request: Request, error: grpc.aio.AioRpcError) -> JSONResponse:
    status = HTTP_STATUS.get(error.code(), 502)
    return JSONResponse(status_code=status, content={"detail": f"flight service: {error.code().name}: {error.details()}"})


@app.exception_handler(BreakerOpen)
async def breaker_open(request: Request, error: BreakerOpen) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(error)})
