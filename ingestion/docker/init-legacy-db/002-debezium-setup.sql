-- Create replication slot for Debezium CDC
SELECT pg_create_logical_replication_slot('debezium_slot', 'pgoutput');

-- Create publication for the orders table
CREATE PUBLICATION debezium_pub FOR TABLE orders;
