from app.tasks import process_webhook, shard_for_customer


def publish_message(message: dict):
    shard = shard_for_customer(message["customer_id"], num_shards=4)
    process_webhook.apply_async(
        args=[message], queue=f"webhook_q_{shard}", routing_key=f"webhook.{shard}"
    )
