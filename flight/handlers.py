from datetime import timezone

import flight_pb2_grpc
import logic
from logic import GrpcError


class Handlers(flight_pb2_grpc.FlightServiceServicer):
    def __init__(self, db, cache):
        self.db = db
        self.cache = cache

    async def run(self, context, coroutine):
        try:
            return await coroutine
        except GrpcError as error:
            await context.abort(error.code, error.message)

    async def SearchFlights(self, request, context):
        date = request.date.ToDatetime(tzinfo=timezone.utc) if request.HasField("date") else None
        return await self.run(
            context, logic.search_flights(self.db, self.cache, request.origin, request.destination, date)
        )

    async def GetFlight(self, request, context):
        return await self.run(context, logic.get_flight(self.db, self.cache, request.flight_id))

    async def ReserveSeats(self, request, context):
        return await self.run(
            context, logic.reserve_seats(self.db, self.cache, request.flight_id, request.seat_count, request.booking_id)
        )

    async def ReleaseReservation(self, request, context):
        return await self.run(context, logic.release_reservation(self.db, self.cache, request.booking_id))
