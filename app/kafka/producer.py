from confluent_kafka import Producer, KafkaException
import time
import os
import json

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

producer = Producer({
  "bootstrap.servers": KAFKA_BROKER
})

def publish_to_kafka(topic, message, retries=5):
    for attempt in range(retries):
        try:
            producer.produce(topic, json.dumps(message).encode("utf-8"))
            producer.flush()
            break
        except KafkaException as e:
            if attempt < retries - 1:
                print(f"Kafka not ready, retrying... ({attempt+1})")
                time.sleep(2)
            else:
                raise e