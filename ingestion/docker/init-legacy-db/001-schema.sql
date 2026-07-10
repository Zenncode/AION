-- Legacy database schema for CDC capture
-- Debezium requires a primary key on captured tables

CREATE TABLE IF NOT EXISTS orders (
    order_id        BIGSERIAL PRIMARY KEY,
    customer_id     BIGINT NOT NULL,
    product_id      BIGINT NOT NULL,
    quantity        INT NOT NULL DEFAULT 1,
    unit_price      NUMERIC(12,2) NOT NULL,
    total_amount    NUMERIC(12,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    currency        VARCHAR(3) DEFAULT 'EUR',
    status          VARCHAR(20) DEFAULT 'pending',
    region          VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Debezium requires replication slots and publication
ALTER SYSTEM SET wal_level = logical;

CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);

-- Seed with sample data
INSERT INTO orders (customer_id, product_id, quantity, unit_price, currency, status, region)
SELECT
    (random() * 1000)::BIGINT + 1,
    (random() * 500)::BIGINT + 1,
    (random() * 10)::INT + 1,
    (random() * 500 + 10)::NUMERIC(12,2),
    CASE (random() * 3)::INT
        WHEN 0 THEN 'EUR'
        WHEN 1 THEN 'USD'
        WHEN 2 THEN 'GBP'
    END,
    CASE (random() * 4)::INT
        WHEN 0 THEN 'pending'
        WHEN 1 THEN 'confirmed'
        WHEN 2 THEN 'shipped'
        WHEN 3 THEN 'delivered'
    END,
    CASE (random() * 4)::INT
        WHEN 0 THEN 'eu-west'
        WHEN 1 THEN 'eu-central'
        WHEN 2 THEN 'us-east'
        WHEN 3 THEN 'ap-south'
    END
FROM generate_series(1, 1000);
