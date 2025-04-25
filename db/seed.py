from sqlalchemy import create_engine, text
import os, uuid, json

DATABASE_URL = os.getenv("DATABASE_URL")
DLQ_EVENT_ID = "11111111-2222-3333-4444-555555555555"


engine = create_engine(DATABASE_URL)

webhook_secret = os.getenv("WEBHOOK_SECRET", "webhook_secret")


with engine.connect() as conn:
    # clear old data
    conn.execute(text("DELETE FROM webhook_events"))
    conn.execute(text("DELETE FROM webhook_audit"))
    conn.execute(text("DELETE FROM customers"))
    conn.execute(text("DELETE FROM webhook_nonces"))

    conn.commit()

    # insert known customer
    for i in range(4):
        customer_name = f"acme_{i}"
        conn.execute(
            text(
                """
                INSERT INTO customers (name, webhook_secret, created_at)
                VALUES (:name, :secret, now())
                ON CONFLICT (name) DO NOTHING
            """
            ),
            {"name": customer_name, "secret": webhook_secret},
        )

    # insert good webhook for valid test
    payload_valid = {
        "order_id": 1,
        "status": "created",
        "customer_name": "Alice",
        "amount": 99.99,
    }

    conn.execute(
        text(
            """
        INSERT INTO webhook_events (event_id, customer_id, payload, status, created_at)
        VALUES (:event_id, :customer_id, :payload, :status, now())
        ON CONFLICT DO NOTHING
    """
        ),
        {
            "event_id": str(uuid.uuid4()),
            "customer_id": customer_name,
            "payload": json.dumps(payload_valid),
            "status": "pending",
        },
    )

    payload_dlq = {
        "event_id": DLQ_EVENT_ID,
        "order_id": 999,
        "status": "created",
        "customer_name": "TRIGGER_DLQ",
        "amount": 1.23,
    }

    conn.execute(
        text(
            """
        INSERT INTO webhook_events (event_id, customer_id, payload, status, created_at)
        VALUES (:event_id, :customer_id, :payload, :status, now())
        ON CONFLICT DO NOTHING
    """
        ),
        {
            "event_id": DLQ_EVENT_ID,
            "customer_id": "acme_0",
            "payload": json.dumps(payload_dlq),
            "status": "pending",
        },
    )
    conn.commit()

print("✅ Seeded customer + valid + DLQ webhook events.")
