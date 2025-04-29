from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv("DATABASE_URL")


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

print("✅ Seeded customers")
