from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException

from client import FlightClient


async def create_booking(db, flight: FlightClient, data):
    booking_id = uuid4()

    found = await flight.get_flight(str(data.flight_id))
    await flight.reserve_seats(found.id, data.seat_count, str(booking_id))
    total_price = Decimal(found.price) * data.seat_count

    try:
        return await db.fetchrow(
            """
            INSERT INTO bookings (id, user_id, flight_id, passenger_name, passenger_email, seat_count, total_price)
            VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING *
            """,
            booking_id, data.user_id, data.flight_id, data.passenger_name, data.passenger_email,
            data.seat_count, total_price,
        )
    except Exception:
        await flight.release_reservation(str(booking_id))
        raise


async def get_booking(db, booking_id: UUID):
    booking = await db.fetchrow("SELECT * FROM bookings WHERE id = $1", booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail=f"booking {booking_id} not found")
    return booking


async def list_bookings(db, user_id: str):
    return await db.fetch("SELECT * FROM bookings WHERE user_id = $1", user_id)


async def cancel_booking(db, flight: FlightClient, booking_id: UUID):
    async with db.acquire() as conn:
        async with conn.transaction():
            booking = await conn.fetchrow("SELECT * FROM bookings WHERE id = $1 FOR UPDATE", booking_id)
            if booking is None:
                raise HTTPException(status_code=404, detail=f"booking {booking_id} not found")
            if booking["status"] != "CONFIRMED":
                raise HTTPException(status_code=409, detail=f"booking {booking_id} is {booking['status']}")

            await flight.release_reservation(str(booking_id))
            return await conn.fetchrow("UPDATE bookings SET status = 'CANCELLED' WHERE id = $1 RETURNING *", booking_id)
