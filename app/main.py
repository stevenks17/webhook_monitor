from fastapi import FastAPI, Request, Depends
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
async def webhook_listener(request: Request, db=Depends(get_db)):
  body = await request.json()
  event = WebhookEvent(payload=body, status='pending')
  db.add(event)
  db.commit()
  db.refresh(event)

  publish_message({"event_id":event.id, 'payload': body})
  return{"status": "received", "event_id": event.id}