from app.tasks import process_webhook
import secrets


process_webhook.delay(
    {
        "event_id": 9999,
        "customer_id": "acme",
        "payload": {
            "order_id": 999,
            "status": "created",
            "customer_name": "FAIL",
            "amount": 0,
            "nonce": secrets.token_urlsafe(16),
        },
    }
)
print("❌ Sent bad message to trigger DLQ")
