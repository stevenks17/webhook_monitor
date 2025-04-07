import pika
import json
from app.tasks import process_webhook

def publish_message(message: dict):
    process_webhook.delay(message)
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="rabbitmq"))
    channel = connection.channel()

    channel.queue_declare(queue="webhook_queue", durable=True)

    channel.basic_publish(
        exchange='',
        routing_key='webhook_queue',
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,  
        )
    )

    connection.close()
