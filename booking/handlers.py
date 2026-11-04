from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

import flight_pb2 as pb
import logic

router = APIRouter()


class FlightResponse(BaseModel):
    id: UUID
    airline: str
    flight_number: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    total_seats: int
    available_seats: int
    price: Decimal
    status: str


class BookingCreate(BaseModel):
    user_id: str
    flight_id: UUID
    passenger_name: str
    passenger_email: str
    seat_count: int


class BookingResponse(BaseModel):
    id: UUID
    user_id: str
    flight_id: UUID
    passenger_name: str
    passenger_email: str
    seat_count: int
    total_price: Decimal
    status: str


def flight_response(flight: pb.Flight) -> FlightResponse:
    return FlightResponse(
        id=flight.id,
        airline=flight.airline,
        flight_number=flight.flight_number,
        origin=flight.origin,
        destination=flight.destination,
        departure_time=flight.departure_time.ToDatetime(tzinfo=timezone.utc),
        arrival_time=flight.arrival_time.ToDatetime(tzinfo=timezone.utc),
        total_seats=flight.total_seats,
        available_seats=flight.available_seats,
        price=Decimal(flight.price),
        status=pb.FlightStatus.Name(flight.status),
    )


def booking_response(row) -> BookingResponse:
    return BookingResponse(**dict(row))


@router.get("/flights", response_model=list[FlightResponse])
async def search_flights(request: Request, origin: str, destination: str, date: date | None = None):
    found = await request.app.state.flight.search_flights(origin, destination, date)
    return [flight_response(flight) for flight in found.flights]


@router.get("/flights/{flight_id}", response_model=FlightResponse)
async def get_flight(request: Request, flight_id: UUID):
    flight = await request.app.state.flight.get_flight(str(flight_id))
    return flight_response(flight)


@router.post("/bookings", response_model=BookingResponse, status_code=201)
async def create_booking(request: Request, data: BookingCreate):
    booking = await logic.create_booking(request.app.state.db, request.app.state.flight, data)
    return booking_response(booking)


@router.get("/bookings", response_model=list[BookingResponse])
async def list_bookings(request: Request, user_id: str):
    bookings = await logic.list_bookings(request.app.state.db, user_id)
    return [booking_response(booking) for booking in bookings]


@router.get("/bookings/{booking_id}", response_model=BookingResponse)
async def get_booking(request: Request, booking_id: UUID):
    booking = await logic.get_booking(request.app.state.db, booking_id)
    return booking_response(booking)


@router.post("/bookings/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(request: Request, booking_id: UUID):
    booking = await logic.cancel_booking(request.app.state.db, request.app.state.flight, booking_id)
    return booking_response(booking)
