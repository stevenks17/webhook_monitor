from confluent_kafka import Producer, KafkaException
import time
import os
import json

import logging


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("kafka_producer")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

producer = Producer({"bootstrap.servers": KAFKA_BROKER})


def publish_to_kafka(topic, message, retries=5):
    for attempt in range(retries):
        try:
            producer.produce(topic, json.dumps(message).encode("utf-8"))
            break
        except KafkaException as e:
            if attempt < retries - 1:
                logger.warning(f"Kafka not ready, retrying... ({attempt+1})")
                time.sleep(2)
            else:
                raise e
    producer.flush()
