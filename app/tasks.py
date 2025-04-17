from celery import Celery, Task
from app.utils import SessionLocal, WebhookEvent
from app.kafka.dlq import publish_to_dlq
import datetime
import json
import random
import logging

logger = logging.getLogger(__name__)

app = Celery(
    "worker",
    broker="pyamqp://guest@rabbitmq//",
    broker_connection_retry_on_startup=True
)

class BasicTaskWithRetry(Task):
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_back_off = True
    retry_jitter = True


@app.task(bind=True, base=BasicTaskWithRetry, queue="webhook_queue")
def process_webhook(self, message):
    db = SessionLocal()
    event = None

    try:
        event_id = message.get("event_id")
        customer_id = message.get("customer_id")
        payload = message.get("payload")

        event = db.query(WebhookEvent).filter(
            WebhookEvent.id == event_id, 
            WebhookEvent.customer_id == customer_id
        ).first()

        if not event:
            logger.warning(f"DLQ Candidate: No event found for ID={event_id}, customer={customer_id}")
            raise ValueError(f"Event {event_id} not found in database!")
        logger.info(f"Processing webhook for customer {customer_id}:{json.dumps(payload)}")
        event.status = "processed"
        event.processed_at = datetime.datetime.utcnow()
        db.commit()
    except Exception as e:
        db.rollback()
        retry_count = self.request.retries
        logger.exception(f"❌ Failed to process webhook (attempt {retry_count}): {e}")

        publish_to_dlq(reason=f"{str(e)} after {retry_count} retries", event_data=message)     

        if event:
            event.status = "retrying"
            db.commit()

        raise self.retry(exc=e)
    
    finally:
        db.close()

