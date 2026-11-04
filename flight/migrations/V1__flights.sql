CREATE TYPE flight_status AS ENUM ('SCHEDULED', 'DEPARTED', 'CANCELLED', 'COMPLETED');

CREATE TABLE flights (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    airline text NOT NULL CHECK (airline ~ '^[A-Z0-9]{2}$'),
    flight_number text NOT NULL,
    origin text NOT NULL CHECK (origin ~ '^[A-Z]{3}$'),
    destination text NOT NULL CHECK (destination ~ '^[A-Z]{3}$'),
    departure_time timestamptz NOT NULL,
    arrival_time timestamptz NOT NULL,
    total_seats integer NOT NULL CHECK (total_seats > 0),
    available_seats integer NOT NULL CHECK (available_seats >= 0 AND available_seats <= total_seats),
    price numeric(12, 2) NOT NULL CHECK (price > 0),
    status flight_status NOT NULL DEFAULT 'SCHEDULED',
    CHECK (origin <> destination),
    CHECK (arrival_time > departure_time)
);

CREATE UNIQUE INDEX flights_number_date
    ON flights (airline, flight_number, ((departure_time AT TIME ZONE 'UTC')::date));
