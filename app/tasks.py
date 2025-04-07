from celery import Celery, Task
from app.utils import SessionLocal, WebhookEvent
import datetime
import json
import random
import logging

logger = logging.getLogger(__name__)

app = Celery(
    "worker",
    broker="pyamqp://guest@rabbitmq//"
)

class BasicTaskWithRetry(Task):
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_back_off = True
    retry_jitter = True


@app.task(bind=True, base=BasicTaskWithRetry)
def process_webhook(self, message):
    db = SessionLocal()

    try:
        event_id = message.get("event_id")
        payload = message.get("payload")
        event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
        if not event:
            logger.info(f"Event {event_id} not found in database!")
            return
        logger.info(f"Processing webhook:{json.dumps(payload)}")

        if random.random() < 0.5:
            raise Exception('Simulated random processing failure')

        event.status = "processed"
        event.processed_at = datetime.datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f'Error processing webhook: {e}')
        db.rollback()
        if event:
            event.status = "retrying"
            db.commit()
        raise self.retry(exc=e)
    finally:
        db.close()

