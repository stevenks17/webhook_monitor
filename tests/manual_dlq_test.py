from app.kafka.dlq import publish_to_dlq
publish_to_dlq("manual test", {"test": "value"})
print("✅ Sent manual DLQ message")
