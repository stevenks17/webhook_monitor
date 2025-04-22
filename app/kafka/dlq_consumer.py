from confluent_kafka import Consumer
import sys
import signal
import json
import logging


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("dlq_consumer")


consumer = Consumer(
    {
        "bootstrap.servers": "kafka:9092",
        "group.id": "dlq-debug",
        "auto.offset.reset": "earliest",
    }
)
consumer.subscribe(["webhook_dlq"])


def shutdown():
    logger.info("Shutting down dlq_consumer...")
    consumer.close()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

logger.info("👀 Listening to DLQ...")

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        logger.error(f"Consumer error: {msg.error()}")
        continue
    try:
        event = json.loads(msg.value().decode("utf-8"))
        logger.info(f"DLQ Event: {event}")
    except Exception as e:
        logger.exception(f"Error processing DLQ message: {e}")
