from app.utils import SessionLocal, WebhookEvent, WebHookPayload, verify_hmac
from fastapi import (
    FastAPI,
    Request,
    Depends,
    Query,
    Header,
    HTTPException,
    BackgroundTasks,
)
from fastapi.responses import JSONResponse
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator
from app.kafka.producer import publish_to_kafka
from app.producer import publish_message
from sqlalchemy import text
import os

ENV = os.getenv("ENV", "development")

app = FastAPI()
Instrumentator().instrument(app).expose(app)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return {"message": "Webhook Monitor is alive!"}


from secrets import token_hex


@app.post("/customers")
def create_customer(name: str, db=Depends(get_db)):
    secret = token_hex(32)

    db.execute(
        text(
            """
        INSERT INTO customers (name, webhook_secret)
        VALUES (:name, :secret)
    """
        ),
        {"name": name, "secret": secret},
    )
    db.commit()

    return {
        "customer_id": name,
        "webhook_secret": secret,
        "message": "Customer created",
    }


webhooks_received = Counter("webhooks_received", "Total number of webhooks received")


@app.post("/webhook")
async def webhook_listener(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: WebHookPayload,
    customer_id: str = Query(...),
    x_delivery_id: str = Header(..., alias="X-Delivery-Id"),
    x_signature: str = Header(..., alias="X-Signature"),
    db=Depends(get_db),
):
    webhooks_received.inc()
    raw_body = await request.body()
    result = db.execute(
        text("SELECT webhook_secret FROM customers WHERE name = :name"),
        {"name": customer_id},
    ).fetchone()

    if not result:
        if ENV != "production":
            generated_secret = os.getenv("WEBHOOK_SECRET")
            db.execute(
                text(
                    """
            INSERT INTO customers (name, webhook_secret) VALUES (:name, :secret) ON CONFLICT (name) DO NOTHING
        """
                ),
                {"name": customer_id, "secret": generated_secret},
            )
            db.commit()
            result = db.execute(
                text("SELECT webhook_secret FROM customers WHERE name = :name"),
                {"name": customer_id},
            ).fetchone()
        else:
            raise HTTPException(status_code=403, detail="Missing webhook secret.")

    webhook_secret = result[0]

    if not verify_hmac(webhook_secret, raw_body, x_signature):
        db.execute(
            text(
                """
            UPDATE customers SET hmac_fail_count = hmac_fail_count + 1 WHERE name = :name
        """
            ),
            {"name": customer_id},
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Invalid signature.")

    db.execute(
        text(
            """
    UPDATE customers SET last_accessed_at = now() WHERE name = :name
    """
        ),
        {"name": customer_id},
    )

    result = db.execute(
        text(
            """
        INSERT INTO delivery_ids(customer_id, delivery_id)
        VALUES (:customer_id, :delivery_id)
        ON CONFLICT (customer_id, delivery_id) DO UPDATE
        SET attempt_count = delivery_ids.attempt_count + 1
        RETURNING id, xmax = 0 as inserted
        """
        ),
        {"customer_id": customer_id, "delivery_id": x_delivery_id},
    )

    row = result.mappings().fetchone()
    if not row or not row["inserted"]:
        raise HTTPException(status_code=409, detail="Duplicate delivery ID")

    event = WebhookEvent(
        payload=payload.model_dump(), status="pending", customer_id=customer_id
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    background_tasks.add_task(
        publish_to_kafka,
        "webhook_events",
        {
            "event_id": event.id,
            "customer_id": customer_id,
            "payload": payload.model_dump(),
        },
    )
    background_tasks.add_task(
        publish_message,
        {
            "event_id": event.id,
            "customer_id": customer_id,
            "payload": payload.model_dump(),
        },
    )

    return JSONResponse({"status": "queued", "event_id": event.id}, status_code=202)


@app.get("/webhooks")
def get_webhooks(customer_id: str, db=Depends(get_db)):
    events = (
        db.query(WebhookEvent).filter(WebhookEvent.customer_id == customer_id).all()
    )
    return {
        "webhooks": [
            {
                "id": e.id,
                "customer_id": e.customer_id,
                "payload": e.payload,
                "status": e.status,
                "created_at": e.created_at,
                "processed_at": e.processed_at,
            }
            for e in events
        ]
    }
