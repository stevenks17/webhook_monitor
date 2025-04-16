from confluent_kafka import Consumer
from colorama import init, Fore, Style
import json
import os

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")


consumer = Consumer ({
    'bootstrap.servers': KAFKA_BROKER,
    'group.id': 'webhook-debug',
    'auto.offset.reset': 'earliest'
})
consumer.subscribe(['webhook_events'])

print("👀 Listening to 'webhook_events'...")
print("Using Kafka broker:", KAFKA_BROKER)


while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        print(f"{Fore.RED}❌ Error: {msg.error()}")
        continue

    try:
        payload = json.loads(msg.value().decode('utf-8'))
        pretty = json.dumps(payload, indent=2)
        print(f"{Fore.GREEN}📨 Received:\n{Fore.CYAN}{pretty}\n{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Failed to parse message: {e}")
