from fastapi import FastAPI, Request, Depends, Query, Header, HTTPException
from app.producer import publish_message
from app.utils import SessionLocal, WebhookEvent, WebHookPayload, verify_hmac_signature
from sqlalchemy import text
from app.kafka.producer import publish_to_kafka
import os

ENV = os.getenv("ENV", "development")

app = FastAPI()

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

    db.execute(text("""
        INSERT INTO customers (name, webhook_secret)
        VALUES (:name, :secret)
    """), {"name": name, "secret": secret})
    db.commit()

    return {
        "customer_id": name,
        "webhook_secret": secret,  
        "message": "Customer created"
    }


@app.post("/webhook")
async def webhook_listener(
    request: Request,
    payload: WebHookPayload,
    customer_id: str = Query(...),
    x_delivery_id: str = Header(..., alias="X-Delivery-Id"),
    x_signature: str = Header(..., alias="X-Signature"),
    db=Depends(get_db)

):
  raw_body = await request.body()
  result = db.execute(text(
     "SELECT webhook_secret FROM customers WHERE name = :name"
  ), {"name": customer_id}).fetchone()

  if not result:
    if ENV != "production":
        db.execute(text("""
            INSERT INTO customers (name) VALUES (:name)
        """), {"name": customer_id})
        db.commit()
        result = db.execute(text(
            "SELECT webhook_secret FROM customers WHERE name = :name"
        ), {"name": customer_id}).fetchone()
    else:
        raise HTTPException(status_code=403, detail="Missing webhook secret.")
  
  webhook_secret = result[0]

  if not verify_hmac_signature(webhook_secret, raw_body, x_signature):
        db.execute(text("""
            UPDATE customers SET hmac_fail_count = hmac_fail_count + 1 WHERE name = :name
        """), {"name": customer_id})
        db.commit()
        raise HTTPException(status_code=403, detail="Invalid signature.")
  
  db.execute(text("""
    UPDATE customers SET last_accessed_at = now() WHERE name = :name
    """), {"name": customer_id})
  

  existing_delivery = db.execute(text(
    "SELECT id, attempt_count FROM delivery_ids WHERE delivery_id = :delivery_id AND customer_id = :customer_id"),
    {"delivery_id": x_delivery_id, "customer_id": customer_id}
    ).fetchone()

  if existing_delivery:
    db.execute(text(
    "UPDATE delivery_ids SET attempt_count = attempt_count + 1 WHERE id = :id"),
    {"id": existing_delivery[0]}
    )
    raise HTTPException(status_code=409, detail="Duplicate delivery ID")

  db.execute(text(
     "INSERT INTO delivery_ids(customer_id, delivery_id) VALUES (:customer_id, :delivery_id)"),
        {"customer_id": customer_id, "delivery_id": x_delivery_id}
    )

  event = WebhookEvent(payload=payload.model_dump(), status='pending', customer_id=customer_id)
  db.add(event)
  db.commit()
  db.refresh(event)

  publish_to_kafka("webhook_events", {
    "event_id": event.id,
    "customer_id": customer_id,
    "payload": payload.model_dump()
  })

  publish_message({"event_id":event.id, "customer_id": customer_id, 'payload': payload.model_dump()})
  return {"status": "received", "event_id": event.id}


@app.get("/webhooks")
def get_webhooks(customer_id:str, db=Depends(get_db)):
    events = db.query(WebhookEvent).filter(WebhookEvent.customer_id == customer_id).all()
    return {"webhooks": [
        {
            "id": e.id,
            "customer_id": e.customer_id,
            "payload": e.payload,
            "status": e.status,
            "created_at": e.created_at,
            "processed_at": e.processed_at
        } for e in events
    ]}