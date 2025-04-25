import os
import time
import datetime
import json

from celery import Celery, Task
from celery.utils.log import get_task_logger
from sqlalchemy import text
from kombu import Exchange, Queue
from app.utils import SessionLocal, WebhookEvent
from app.kafka.dlq import publish_to_dlq

from prometheus_client import (
    CollectorRegistry,
    multiprocess,
    Counter,
    Histogram,
    start_http_server,
)

logger = get_task_logger(__name__)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "pyamqp://guest@rabbitmq//")

# ─── Prometheus multiprocess setup ─────────────────────────────────────────────
if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)

    webhooks_processing_latency = Histogram(
        "webhook_processing_latency_seconds",
        "Webhook end-to-end processing time",
        registry=registry,
    )
    webhooks_processed = Counter(
        "webhooks_processed_total", "Total webhooks processed", registry=registry
    )
    webhooks_failed = Counter(
        "webhooks_failed_total", "Total webhooks failed", registry=registry
    )
else:
    registry = None
    webhooks_processing_latency = Histogram(
        "webhook_processing_latency_seconds", "Webhook end-to-end processing time"
    )
    webhooks_processed = Counter("webhooks_processed_total", "Total webhooks processed")
    webhooks_failed = Counter("webhooks_failed_total", "Total webhooks failed")

if os.getenv("RUN_PROM_METRICS", "false").lower() == "true":
    start_http_server(8005, registry=registry)

# ─── Celery app setup ──────────────────────────────────────────────────────────
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


UPSERT_WEBHOOK = text(
    """
    INSERT INTO webhook_events
      (event_id, customer_id, payload, status, created_at, processed_at)
    VALUES
      (:event_id, :customer_id, :payload, 'processed', now(), now())
    ON CONFLICT (event_id) DO UPDATE
      SET processed_at = now()
"""
)


class BasicTaskWithRetry(Task):
    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True
    retry_jitter = True


@app.task(bind=True, base=BasicTaskWithRetry)
def process_webhook(self, message):
    start = time.monotonic()
    try:
        with SessionLocal() as db:
            event_id = message["event_id"]
            customer_id = message["customer_id"]
            payload = json.dumps(message["payload"])

            db.execute(
                UPSERT_WEBHOOK,
                {
                    "event_id": event_id,
                    "customer_id": customer_id,
                    "payload": payload,
                },
            )
            db.commit()

            logger.info(f"Processing webhook {event_id} for {customer_id}")
            webhooks_processed.inc()

    except Exception as e:
        webhooks_failed.inc()
        retry_count = self.request.retries
        logger.exception(f"❌ Failed to process webhook (attempt {retry_count}): {e}")

        publish_to_dlq(
            reason=f"{str(e)} after {retry_count} retries", event_data=message
        )

        raise self.retry(exc=e)

    finally:
        webhooks_processing_latency.observe(time.monotonic() - start)


@app.task
def increment_hmac_fail(customer_id: str):
    with SessionLocal() as db:
        db.execute(
            text(
                "UPDATE customers SET hmac_fail_count = hmac_fail_count+1 WHERE name=:n"
            ),
            {"n": customer_id},
        )
        db.commit()


@app.task
def update_last_accessed(customer_id: str):
    with SessionLocal() as db:
        db.execute(
            text("UPDATE customers SET last_accessed_at = now() WHERE name = :n"),
            {"n": customer_id},
        )
        db.commit()


def shard_for_customer(customer_id: str, num_shards: int = 4) -> int:
    return hash(customer_id) % num_shards
