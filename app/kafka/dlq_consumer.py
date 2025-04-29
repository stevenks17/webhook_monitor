import os
import json
import secrets
import uuid

import pytest
import requests
from confluent_kafka import Consumer

BACKEND_URL = "http://backend:8000"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "webhook_secret")
DLQ_TOPIC = "webhook_events_dlq"
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")


@pytest.fixture(scope="module")
def kafka_consumer():
    c = Consumer(
        {
            "bootstrap.servers": KAFKA_BROKER,
            "group.id": "dlq_test_suite",
            "auto.offset.reset": "earliest",
        }
    )
    c.subscribe([DLQ_TOPIC])
    yield c
    c.close()


def test_hmac_fail_goes_to_dlq(kafka_consumer):
    payload = {
        "order_id": 999,
        "status": "created",
        "customer_name": "DLQ_TRIGGER",
        "amount": 1.23,
        "nonce": secrets.token_urlsafe(8),
    }
    raw = json.dumps(payload).encode("utf-8")

    bad_sig = "0" * 64

    resp = requests.post(
        f"{BACKEND_URL}/webhook?customer_id=acme",
        headers={
            "X-Delivery-Id": str(uuid.uuid4()),
            "X-Signature": bad_sig,
            "Content-Type": "application/json",
        },
        data=raw,
    )
    assert resp.status_code == 403

    msg = kafka_consumer.poll(timeout=10.0)
    assert msg is not None, "No message in DLQ topic"
    assert not msg.error()

    data = json.loads(msg.value().decode("utf-8"))
    assert data.get("order_id") == 999
    assert data.get("hmac_failed", True), "DLQ message should be marked hmac_failed"
