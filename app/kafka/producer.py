from confluent_kafka import Producer
import os
import json

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

producer = Producer({
  "bootstrap.servers": KAFKA_BROKER
})

def publish_to_kafka(topic:str, message:dict):
  producer.produce(topic, value=json.dumps(message).encode("utf-8"))
  producer.flush()