from confluent_kafka import Consumer
import json

consumer = Consumer({
    'bootstrap.servers': 'kafka:9092',
    'group.id': 'dlq-debug',
    'auto.offset.reset': 'earliest'
})
consumer.subscribe(['webhook_dlq'])

print("👀 Listening to DLQ...")

while True:
    msg = consumer.poll(1.0)
    print(".", end="", flush=True)  # This line will print dots every second
    if msg is None:
        continue
    if msg.error():
        print("❌", msg.error())
        continue
    print("\n DLQ Event:", json.loads(msg.value().decode('utf-8')))

