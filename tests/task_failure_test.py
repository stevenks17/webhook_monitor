import json, logging
import pytest
from celery.exceptions import Retry
from app.tasks import app, process_webhook, webhooks_failed

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def configure_celery():
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True


class BadSessionLocal:
    def __enter__(self):
        raise RuntimeError("DB down")

    def __exit__(self, exc_type, exc, tb):
        return False


dlq_calls = []


def fake_publish_to_dlq(reason, event_data):
    dlq_calls.append((reason, event_data))


@pytest.fixture(autouse=True)
def patch_failures(monkeypatch):
    monkeypatch.setattr("app.tasks.SessionLocal", BadSessionLocal)
    monkeypatch.setattr(
        "app.kafka.dlq.publish_to_dlq", fake_publish_to_dlq, raising=True
    )
    yield
    dlq_calls.clear()


def test_process_webhook_retries_and_dlq(caplog):
    caplog.set_level(logging.INFO)
    before_failed = webhooks_failed._value.get()
    logger.info(f"webhooks_failed before: {before_failed}")

    message = {
        "event_id": "evt-1",
        "customer_id": "cust-1",
        "payload": {"foo": "bar"},
        "raw_body": json.dumps({"foo": "bar"}),
        "x_signature": "sig",
    }

    with pytest.raises(Retry):
        process_webhook.apply(args=[message])

    assert len(dlq_calls) == 1, f"Expected 1 DLQ call, got {len(dlq_calls)}"
    reason, evt = dlq_calls[0]
    assert "DB down" in reason, f"Unexpected DLQ reason: {reason}"
    assert evt == message, "DLQ event data mismatch"

    after_failed = webhooks_failed._value.get()
    logger.info(f"webhooks_failed after: {after_failed}")
    assert (
        after_failed > before_failed
    ), f"webhooks_failed did not increment: {before_failed} -> {after_failed}"

    logger.info(f"DLQ calls: {len(dlq_calls)} -> reason: {reason}")

    assert "webhooks_failed before:" in caplog.text
    assert "webhooks_failed after:" in caplog.text
    assert "DLQ calls:" in caplog.text
