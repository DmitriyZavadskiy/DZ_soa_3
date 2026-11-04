import asyncio
import logging
import os

import asyncpg
import grpc

import flight_pb2_grpc
from auth import AuthInterceptor
from cache import Cache
from handlers import Handlers

log = logging.getLogger("flight")


async def main() -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s %(message)s")

    db = await asyncpg.create_pool(os.environ["DATABASE_URL"])
    cache = Cache(
        os.environ["SENTINEL_HOST"],
        int(os.environ["SENTINEL_PORT"]),
        os.environ["MASTER_NAME"],
        int(os.environ["CACHE_TTL_SECONDS"]),
    )

    server = grpc.aio.server(interceptors=[AuthInterceptor(os.environ["API_KEY"])])
    flight_pb2_grpc.add_FlightServiceServicer_to_server(Handlers(db, cache), server)
    server.add_insecure_port("[::]:50051")

    await server.start()
    log.info("grpc server started on port 50051")
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(main())
