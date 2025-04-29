from app.utils import SessionLocal, WebhookEvent, WebHookPayload, verify_hmac
from app.tasks import shard_for_customer, process_webhook
from fastapi import (
    FastAPI,
    Request,
    Depends,
    Query,
    Header,
    HTTPException,
)
from fastapi.responses import JSONResponse
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator
from app.kafka.producer import publish_to_kafka
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from secrets import token_hex
import os, uuid


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
    yield db
    db.close()


@app.get("/")
def read_root():
    return {"message": "Webhook Monitor is alive!"}


def record_audit(event_id: str, customer_id: str, raw_body: str, x_signature: str):
    with SessionLocal() as db:
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
                "raw_body": raw_body,
                "x_signature": x_signature,
            },
        )
        db.commit()


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
    payload: WebHookPayload,
    customer_id: str = Query(...),
    x_signature: str = Header(..., alias="X-Signature"),
    db=Depends(get_db),
):
    webhooks_received.inc()
    raw_body = await request.body()
    event_id = str(uuid.uuid4())

    try:
        db.execute(
            text("INSERT INTO webhook_nonces(customer_id,nonce) VALUES(:cid,:nonce)"),
            {"cid": customer_id, "nonce": payload.nonce},
        )
        db.commit()
    except IntegrityError:
        webhook_duplicate.inc()
        raise HTTPException(409, "Duplicate nonce")

    row = db.execute(
        text("SELECT webhook_secret FROM customers WHERE name=:n"),
        {"n": customer_id},
    ).fetchone()
    if not row and os.getenv("ENV", "dev") != "production":
        db.execute(
            text(
                """
                INSERT INTO customers(name,webhook_secret)
                VALUES(:n,:s) ON CONFLICT DO NOTHING
            """
            ),
            {"n": customer_id, "s": os.getenv("WEBHOOK_SECRET", "secret")},
        )
        db.commit()
        row = db.execute(
            text("SELECT webhook_secret FROM customers WHERE name=:n"),
            {"n": customer_id},
        ).fetchone()
    if not row:
        raise HTTPException(403, "Unknown customer")

    secret = row[0]
    if not verify_hmac(secret, raw_body, x_signature):
        webhook_hmac_fail.inc()
        bad_msg = {
            "event_id": event_id,
            "customer_id": customer_id,
            "payload": payload.model_dump(),
            "raw_body": raw_body.decode(),
            "x_signature": x_signature,
            "hmac_failed": True,
        }
        process_webhook.apply_async(
            args=(bad_msg,),
            queue=f"webhook_q_{shard_for_customer(customer_id)}",
        )
        raise HTTPException(403, "Invalid signature")

    message = {
        "event_id": event_id,
        "customer_id": customer_id,
        "payload": payload.model_dump(),
        "raw_body": raw_body.decode(),
        "x_signature": x_signature,
    }
    publish_to_kafka("webhook_events", message)
    return {"status": "queued", "event_id": event_id}


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
