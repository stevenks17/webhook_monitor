from fastapi import FastAPI, Request, Depends, Query
from app.producer import publish_message
from app.utils import SessionLocal, WebhookEvent


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
    request: Request,
    customer_id: str = Query("default"),
    db=Depends(get_db)

):
  body = await request.json()
  event = WebhookEvent(payload=body, status='pending', customer_id=customer_id)
  db.add(event)
  db.commit()
  db.refresh(event)

  publish_message({"event_id":event.id, "customer_id": customer_id, 'payload': body})
  return{"status": "received", "event_id": event.id}

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