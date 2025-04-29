import time
import secrets
import random
import uuid
import json

import pytest
from app.tasks import app, process_webhook


@pytest.fixture(autouse=True)
def configure_celery():
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True


def test_process_webhook_latency():
    N = 100
    CUSTOMER_IDS = [f"acme_{i}" for i in range(4)]
    latencies = []

    for i in range(N):
        message = {
            "event_id": str(uuid.uuid4()),
            "customer_id": random.choice(CUSTOMER_IDS),
            "raw_body": json.dumps({"order_id": i, "test": True}),
            "x_signature": "test-signature",
            "payload": {
                "order_id": i,
                "status": "created",
                "customer_name": f"User-{i}",
                "amount": round(10 + i * 0.5, 2),
                "nonce": secrets.token_urlsafe(16),
            },
        }
        start = time.monotonic()
        process_webhook.apply_async(args=[message])
        latencies.append(time.monotonic() - start)

    latencies.sort()
    count = len(latencies)

    p50 = latencies[int(0.50 * count)]
    p95 = latencies[int(0.95 * count)]
    p99 = latencies[int(0.99 * count)]

    print(f"p50 latency: {p50:.3f}s")
    print(f"p95 latency: {p95:.3f}s")
    print(f"p99 latency: {p99:.3f}s")

    assert p99 < 3.0, f"p99 latency is too high: {p99:.3f}s"
