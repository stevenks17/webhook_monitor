from sqlalchemy import create_engine, text
from datetime import datetime
import json
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

customer_name = "acme"
webhook_secret = "326487fb39a7bdfa85836046c9df5c42b8eafb192af16621df080f1b6f940b20"

with engine.connect() as conn:
    # clear old data
    conn.execute(text("DELETE FROM webhook_events"))
    conn.execute(text("DELETE FROM delivery_ids"))
    conn.execute(text("DELETE FROM customers"))
    conn.commit()

    # insert known customer
    conn.execute(text("""
        INSERT INTO customers (name, webhook_secret, created_at)
        VALUES (:name, :secret, now())
        ON CONFLICT (name) DO NOTHING
    """), {"name": customer_name, "secret": webhook_secret})

    # insert good webhook for valid test
    payload_valid = {
        "order_id": 1,
        "status": "created",
        "customer_name": "Alice",
        "amount": 99.99
    }

    conn.execute(text("""
        INSERT INTO webhook_events (id, customer_id, payload, status, created_at)
        VALUES (:id, :customer_id, :payload, :status, now())
        ON CONFLICT DO NOTHING
    """), {
        "id": 1001,
        "customer_id": customer_name,
        "payload": json.dumps(payload_valid),
        "status": "pending"
    })

    # insert DLQ trigger webhook
    payload_dlq = {
        "order_id": 123,
        "status": "created",
        "customer_name": "TRIGGER_DLQ",
        "amount": 49.99
    }

    conn.execute(text("""
        INSERT INTO webhook_events (id, customer_id, payload, status, created_at)
        VALUES (:id, :customer_id, :payload, :status, now())
        ON CONFLICT DO NOTHING
    """), {
        "id": 1234,
        "customer_id": customer_name,
        "payload": json.dumps(payload_dlq),
        "status": "pending"
    })

    conn.commit()

print("✅ Seeded customer + valid + DLQ webhook events.")
