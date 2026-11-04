CREATE TYPE booking_status AS ENUM ('CONFIRMED', 'CANCELLED');

CREATE TABLE bookings (
    id uuid PRIMARY KEY,
    user_id text NOT NULL,
    flight_id uuid NOT NULL,
    passenger_name text NOT NULL,
    passenger_email text NOT NULL,
    seat_count integer NOT NULL CHECK (seat_count > 0),
    total_price numeric(12, 2) NOT NULL CHECK (total_price > 0),
    status booking_status NOT NULL DEFAULT 'CONFIRMED'
);

CREATE INDEX bookings_user_id ON bookings (user_id);
