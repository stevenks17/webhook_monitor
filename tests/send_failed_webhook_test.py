from app.tasks import process_webhook

process_webhook.delay({
    "event_id": 9999,  
    "customer_id": "acme",
    "payload": {
        "order_id": 999,
        "status": "created",
        "customer_name": "FAIL",
        "amount": 0
    }
})
print("❌ Sent bad message to trigger DLQ")
