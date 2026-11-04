import uuid
from datetime import datetime, timedelta, timezone

import grpc

import flight_pb2 as pb
from cache import Cache, flight_key, search_key


class GrpcError(Exception):
    def __init__(self, code: grpc.StatusCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def parse_uuid(value: str, name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise GrpcError(grpc.StatusCode.INVALID_ARGUMENT, f"{name} must be a uuid")


def to_flight(row) -> pb.Flight:
    flight = pb.Flight(
        id=str(row["id"]),
        airline=row["airline"],
        flight_number=row["flight_number"],
        origin=row["origin"],
        destination=row["destination"],
        total_seats=row["total_seats"],
        available_seats=row["available_seats"],
        price=str(row["price"]),
        status=pb.FlightStatus.Value(row["status"]),
    )
    flight.departure_time.FromDatetime(row["departure_time"])
    flight.arrival_time.FromDatetime(row["arrival_time"])
    return flight


def to_reservation(row) -> pb.SeatReservation:
    return pb.SeatReservation(
        id=str(row["id"]),
        flight_id=str(row["flight_id"]),
        booking_id=str(row["booking_id"]),
        seat_count=row["seat_count"],
        status=pb.ReservationStatus.Value(row["status"]),
    )


def cache_keys(flight) -> list[str]:
    day = flight["departure_time"].astimezone(timezone.utc).strftime("%Y-%m-%d")
    return [
        flight_key(flight["id"]),
        search_key(flight["origin"], flight["destination"], day),
        search_key(flight["origin"], flight["destination"], None),
    ]


async def search_flights(db, cache: Cache, origin: str, destination: str, date: datetime | None) -> pb.SearchResponse:
    if not origin or not destination:
        raise GrpcError(grpc.StatusCode.INVALID_ARGUMENT, "origin and destination are required")
    day = date.strftime("%Y-%m-%d") if date else None

    key = search_key(origin, destination, day)
    cached = await cache.get(key, pb.SearchResponse())
    if cached is not None:
        return cached

    sql = "SELECT * FROM flights WHERE origin = $1 AND destination = $2 AND status = 'SCHEDULED'"
    args = [origin, destination]
    if date is not None:
        day_start = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
        sql += " AND departure_time >= $3 AND departure_time < $4"
        args += [day_start, day_start + timedelta(days=1)]
    sql += " ORDER BY departure_time"
    rows = await db.fetch(sql, *args)

    response = pb.SearchResponse(flights=[to_flight(row) for row in rows])
    await cache.set(key, response)
    return response


async def get_flight(db, cache: Cache, flight_id: str) -> pb.Flight:
    flight_uuid = parse_uuid(flight_id, "flight_id")

    key = flight_key(flight_uuid)
    cached = await cache.get(key, pb.Flight())
    if cached is not None:
        return cached

    row = await db.fetchrow("SELECT * FROM flights WHERE id = $1", flight_uuid)
    if row is None:
        raise GrpcError(grpc.StatusCode.NOT_FOUND, f"flight {flight_id} not found")

    flight = to_flight(row)
    await cache.set(key, flight)
    return flight


async def reserve_seats(db, cache: Cache, flight_id: str, seat_count: int, booking_id: str) -> pb.SeatReservation:
    flight_uuid = parse_uuid(flight_id, "flight_id")
    booking_uuid = parse_uuid(booking_id, "booking_id")
    if seat_count < 1:
        raise GrpcError(grpc.StatusCode.INVALID_ARGUMENT, "seat_count must be positive")

    async with db.acquire() as conn:
        async with conn.transaction():
            flight = await conn.fetchrow("SELECT * FROM flights WHERE id = $1 FOR UPDATE", flight_uuid)
            if flight is None:
                raise GrpcError(grpc.StatusCode.NOT_FOUND, f"flight {flight_id} not found")

            existing = await conn.fetchrow("SELECT * FROM seat_reservations WHERE booking_id = $1", booking_uuid)
            if existing is not None:
                return to_reservation(existing)

            if flight["status"] != "SCHEDULED":
                raise GrpcError(grpc.StatusCode.FAILED_PRECONDITION, f"flight {flight_id} is {flight['status']}")
            if flight["available_seats"] < seat_count:
                raise GrpcError(
                    grpc.StatusCode.RESOURCE_EXHAUSTED,
                    f"only {flight['available_seats']} seats available, requested {seat_count}",
                )

            await conn.execute(
                "UPDATE flights SET available_seats = available_seats - $2 WHERE id = $1", flight_uuid, seat_count
            )
            reservation = await conn.fetchrow(
                "INSERT INTO seat_reservations (flight_id, booking_id, seat_count) VALUES ($1, $2, $3) RETURNING *",
                flight_uuid, booking_uuid, seat_count,
            )

    await cache.delete(*cache_keys(flight))
    return to_reservation(reservation)


async def release_reservation(db, cache: Cache, booking_id: str) -> pb.SeatReservation:
    booking_uuid = parse_uuid(booking_id, "booking_id")

    async with db.acquire() as conn:
        async with conn.transaction():
            reservation = await conn.fetchrow(
                "SELECT * FROM seat_reservations WHERE booking_id = $1 FOR UPDATE", booking_uuid
            )
            if reservation is None or reservation["status"] != "ACTIVE":
                raise GrpcError(grpc.StatusCode.NOT_FOUND, f"active reservation for booking {booking_id} not found")

            flight = await conn.fetchrow("SELECT * FROM flights WHERE id = $1 FOR UPDATE", reservation["flight_id"])
            await conn.execute(
                "UPDATE flights SET available_seats = available_seats + $2 WHERE id = $1",
                flight["id"], reservation["seat_count"],
            )
            reservation = await conn.fetchrow(
                "UPDATE seat_reservations SET status = 'RELEASED' WHERE id = $1 RETURNING *", reservation["id"]
            )

    await cache.delete(*cache_keys(flight))
    return to_reservation(reservation)
