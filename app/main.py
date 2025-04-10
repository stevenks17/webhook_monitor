from fastapi import FastAPI, Request, Depends, Query, Header, HTTPException
from app.producer import publish_message
from app.utils import SessionLocal, WebhookEvent, WebHookPayload
from sqlalchemy import text


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

@app.post("/webhook")
async def webhook_listener(
    payload: WebHookPayload,
    customer_id: str = Query("default"),
    x_delivery_id: str = Header("X-Delivery-Id: unique-test-id-123"),
    db=Depends(get_db)

):
  existing_delivery = db.execute(text(
    "SELECT id, attempt_count FROM delivery_ids WHERE delivery_id = :delivery_id AND customer_id = :customer_id"),
    {"delivery_id": x_delivery_id, "customer_id": customer_id}
).fetchone()

  if existing_delivery:
    db.execute(text(
    "UPDATE delivery_ids SET attempt_count = attempt_count + 1 WHERE id = :id"),
    {"id": existing_delivery[0]}
)
    db.commit()
    raise HTTPException(status_code=409, detail="Duplicate delivery ID")

  db.execute(text(
     "INSERT INTO delivery_ids(customer_id, delivery_id) VALUES (:customer_id, :delivery_id)"),
        {"customer_id": customer_id, "delivery_id": x_delivery_id}
)
  db.commit()

  event = WebhookEvent(payload=payload.model_dump(), status='pending', customer_id=customer_id)
  db.add(event)
  db.commit()
  db.refresh(event)

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