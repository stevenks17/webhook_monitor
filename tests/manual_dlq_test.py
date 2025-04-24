import requests
import hmac, hashlib, json, os

webhook_secret = os.getenv("WEBHOOK_SECRET", "webhook_secret")
DLQ_EVENT_ID = "11111111-2222-3333-4444-555555555555"

payload = {
    "event_id": DLQ_EVENT_ID,
    "order_id": 999,
    "status": "created",
    "customer_name": "TRIGGER_DLQ",
    "amount": 1.23,
}

raw_body = json.dumps(payload).encode("utf-8")
signature = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()

response = requests.post(
    "http://localhost:8000/webhook",
    params={"customer_id": "acme"},
    headers={
        "X-Delivery-Id": "dlq-test-1",
        "X-Signature": signature,
    },
    json=payload,
)
print("Webhook sent, response:", response.json())
