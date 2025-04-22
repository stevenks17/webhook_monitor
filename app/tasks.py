from celery import Celery, Task
from prometheus_client import Counter, Histogram, start_http_server
from kombu import Exchange, Queue
from app.utils import SessionLocal, WebhookEvent
from app.kafka.dlq import publish_to_dlq
import datetime
import json, os, logging, time

webhooks_processing_latency = Histogram(
    "webhook_processing_latency_seconds", "Webhook end-to-end processing time"
)
logger = logging.getLogger(__name__)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "pyamqp://guest@rabbitmq//")
if os.getpid() == os.getppid():
    from prometheus_client import start_http_server

    start_http_server(8005)

app = Celery(
    "worker", broker=CELERY_BROKER_URL, broker_connection_retry_on_startup=True
)

app.conf.task_queues = [
    Queue(
        f"webhook_q_{i}",
        Exchange("webhook_exchange"),
        routing_key=f"webhook.{i}",
    )
    for i in range(4)
]
app.conf.task_default_queue = "webhook_q_0"
app.conf.task_default_exchange = "webhook_exchange"
app.conf.task_default_routing_key = "webhook.0"

app.conf.worker_send_task_events = True
app.conf.task_send_sent_event = True


class BasicTaskWithRetry(Task):
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_jitter = True


webhooks_processed = Counter("webhooks_processed_total", "Total webhooks processed")
webhooks_failed = Counter("webhooks_failed_total", "Total webhooks failed")


@app.task(bind=True, base=BasicTaskWithRetry)
def process_webhook(self, message):
    start = time.monotonic()
    event = None
    try:
        with SessionLocal() as db:
            event_id = message.get("event_id")
            customer_id = message.get("customer_id")
            payload = message.get("payload")

            event = (
                db.query(WebhookEvent)
                .filter(
                    WebhookEvent.id == event_id, WebhookEvent.customer_id == customer_id
                )
                .first()
            )

            if not event:
                logger.warning(
                    f"DLQ Candidate: No event found for ID={event_id}, customer={customer_id}"
                )
                raise ValueError(f"Event {event_id} not found in database!")
            logger.info(
                f"Processing webhook for customer {customer_id}:{json.dumps(payload)}"
            )
            event.status = "processed"
            event.processed_at = datetime.datetime.utcnow()
            webhooks_processed.inc()
            db.commit()
    except Exception as e:
        db.rollback()
        retry_count = self.request.retries
        webhooks_failed.inc()
        logger.exception(f"❌ Failed to process webhook (attempt {retry_count}): {e}")

        publish_to_dlq(
            reason=f"{str(e)} after {retry_count} retries", event_data=message
        )

        if event:
            with SessionLocal() as db:
                event_in_db = (
                    db.query(WebhookEvent)
                    .filter(
                        WebhookEvent.id == event.id,
                        WebhookEvent.customer_id == event.customer_id,
                    )
                    .first()
                )
                if event_in_db:
                    event_in_db.status = "retrying"
                    db.commit()

        raise self.retry(exc=e)
    finally:
        webhooks_processing_latency.observe(time.monotonic() - start)


def shard_for_customer(customer_id: str, num_shards: int = 4) -> int:
    return hash(customer_id) % num_shards
