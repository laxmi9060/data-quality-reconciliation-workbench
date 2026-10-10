-- Run this first in PostgreSQL to create the two source tables.

CREATE TABLE IF NOT EXISTS orders (
    transaction_id TEXT,
    order_date DATE,
    customer_id TEXT,
    amount NUMERIC(12, 2),
    currency TEXT
);

CREATE TABLE IF NOT EXISTS payments (
    transaction_id TEXT,
    payment_date DATE,
    customer_id TEXT,
    amount NUMERIC(12, 2),
    currency TEXT
);
