from datetime import date, datetime, timezone

import grpc

import flight_pb2 as pb
import flight_pb2_grpc


class FlightClient:
    def __init__(self, address: str, key: str, timeout: float, interceptors: list):
        self.channel = grpc.aio.insecure_channel(address, interceptors=interceptors)
        self.stub = flight_pb2_grpc.FlightServiceStub(self.channel)
        self.metadata = (("x-api-key", key),)
        self.timeout = timeout

    async def search_flights(self, origin: str, destination: str, day: date | None) -> pb.SearchResponse:
        request = pb.SearchRequest(origin=origin, destination=destination)
        if day is not None:
            request.date.FromDatetime(datetime(day.year, day.month, day.day, tzinfo=timezone.utc))
        return await self.stub.SearchFlights(request, metadata=self.metadata, timeout=self.timeout)

    async def get_flight(self, flight_id: str) -> pb.Flight:
        request = pb.GetFlightRequest(flight_id=flight_id)
        return await self.stub.GetFlight(request, metadata=self.metadata, timeout=self.timeout)

    async def reserve_seats(self, flight_id: str, seat_count: int, booking_id: str) -> pb.SeatReservation:
        request = pb.ReserveRequest(flight_id=flight_id, seat_count=seat_count, booking_id=booking_id)
        return await self.stub.ReserveSeats(request, metadata=self.metadata, timeout=self.timeout)

    async def release_reservation(self, booking_id: str) -> pb.SeatReservation:
        request = pb.ReleaseRequest(booking_id=booking_id)
        return await self.stub.ReleaseReservation(request, metadata=self.metadata, timeout=self.timeout)

    async def close(self) -> None:
        await self.channel.close()
