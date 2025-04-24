from app.utils import SessionLocal, WebhookEvent, WebHookPayload, verify_hmac
from app.tasks import update_last_accessed, increment_hmac_fail, process_webhook
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
import os, uuid

ENV = os.getenv("ENV", "development")

app = FastAPI()
Instrumentator().instrument(app).expose(app)
webhooks_received = Counter(
    "webhooks_received_total", "Total number of webhooks received"
)
webhook_hmac_fail = Counter(
    "webhook_hmac_fail_total", "Number of webhooks rejected due to bad HMAC"
)
webhook_duplicate = Counter(
    "webhook_duplicate_total", "Number of webhooks dropped as duplicate delivery IDs"
)


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
    event_id = str(uuid.uuid4())
    nonce = payload.nonce

    result = db.execute(
        text("SELECT webhook_secret FROM customers WHERE name = :name"),
        {"name": customer_id},
    ).fetchone()

    if not result:
        if ENV != "production":
            generated_secret = os.getenv("WEBHOOK_SECRET", "webhook_secret")
            db.execute(
                text(
                    """
                    INSERT INTO customers(name, webhook_secret)
                    VALUES(:name, :secret)
                    ON CONFLICT DO NOTHING
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
            raise HTTPException(403, "Missing webhook_secret")

    webhook_secret = result[0]

    exists = db.execute(
        text(
            """
        SELECT 1 FROM webhook_events
        WHERE customer_id = :cid AND payload->>'nonce' = :nonce
    """
        ),
        {"cid": customer_id, "nonce": nonce},
    ).fetchone()
    if exists:
        webhook_duplicate.inc()
        raise HTTPException(409, "Duplicate/replayed nonce")

    if not verify_hmac(webhook_secret, raw_body, x_signature):
        webhook_hmac_fail.inc()
        increment_hmac_fail.delay(customer_id)
        raise HTTPException(403, "Invalid signature")

    event_data = {
        "event_id": event_id,
        "customer_id": customer_id,
        "delivery_id": x_delivery_id,
        "payload": payload.model_dump(),
        "raw_body": raw_body.decode(),
        "x_signature": x_signature,
    }

    db.execute(
        text(
            """
            INSERT INTO webhook_audit
                (event_id, customer_id, raw_body, x_signature)
            VALUES
                (:event_id, :customer_id, CAST(:raw_body AS JSONB), :x_signature)
            """
        ),
        {
            "event_id": event_id,
            "customer_id": customer_id,
            "raw_body": raw_body.decode(),
            "x_signature": x_signature,
        },
    )
    db.commit()

    process_webhook.delay(event_data)
    update_last_accessed.delay(customer_id)

    background_tasks.add_task(
        publish_to_kafka,
        "webhook_events",
        event_data,
    )

    background_tasks.add_task(
        publish_message,
        event_data,
    )

    return JSONResponse({"status": "queued", "event_id": event_id})


@app.get("/webhooks")
def get_webhooks(customer_id: str, db=Depends(get_db)):
    events = (
        db.query(WebhookEvent).filter(WebhookEvent.customer_id == customer_id).all()
    )
    return {
        "webhooks": [
            {
                "event_id": e.event_id,
                "customer_id": e.customer_id,
                "payload": e.payload,
                "status": e.status,
                "created_at": e.created_at,
                "processed_at": e.processed_at,
            }
            for e in events
        ]
    }
