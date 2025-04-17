from app.tasks import process_webhook

def publish_message(message: dict):
    process_webhook.delay(message)

