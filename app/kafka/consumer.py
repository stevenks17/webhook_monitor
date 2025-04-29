import os, json, sys
from confluent_kafka import Consumer
from app.tasks import process_webhook, shard_for_customer

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

print("Kafka consumer starting…", flush=True)


conf = {
    "bootstrap.servers": KAFKA_BROKER,
    "group.id": "webhook-workers",
    "auto.offset.reset": "earliest",
}

consumer = Consumer(conf)
consumer.subscribe(["webhook_events"])

try:
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"❌ Consumer error: {msg.error()}", file=sys.stderr)
            continue

        data = json.loads(msg.value().decode("utf-8"))
        shard = shard_for_customer(data["customer_id"])
        process_webhook.apply_async(
            args=[data], queue=f"webhook_q_{shard_for_customer(data['customer_id'])}"
        )
        print(
            f"Received event {data['event_id']} for {data['customer_id']} → queued on webhook_q_{shard}"
        )

finally:
    consumer.close()
