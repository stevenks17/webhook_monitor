from confluent_kafka import Producer
import json
import os


KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

dlq_producer = Producer(
    {
        "bootstrap.servers": KAFKA_BROKER,
    }
)


def publish_to_dlq(reason: str, event_data: dict):
    message = {
        "reason": reason,
        "event_data": event_data,
    }

    dlq_producer.produce("webhook_dlq", value=json.dumps(message).encode("utf-8"))
    dlq_producer.flush()
