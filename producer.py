"""
producer.py — publishes an incoming support ticket to RabbitMQ.

Called by the FastAPI webhook as soon as a Slack message arrives,
so the HTTP response is instant and processing is fully async.
"""

import json
import pika
from config import RABBITMQ_URL, TICKET_QUEUE, PRIORITY_TICKET_QUEUE


def get_channel():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    # Declare both queues (idempotent — safe to call multiple times)
    channel.queue_declare(queue=TICKET_QUEUE, durable=True)
    channel.queue_declare(queue=PRIORITY_TICKET_QUEUE, durable=True)

    return connection, channel


def publish_ticket(ticket: dict, high_priority: bool = False):
    """
    Publish a ticket dict to the appropriate RabbitMQ queue.

    ticket = {
        "complaint_text": str,
        "slack_user_id":  str,
        "slack_channel":  str,
    }

    high_priority tickets go to a separate queue so workers
    can drain them first — critical issues jump the line.
    """
    connection, channel = get_channel()

    queue = PRIORITY_TICKET_QUEUE if high_priority else TICKET_QUEUE

    channel.basic_publish(
        exchange="",
        routing_key=queue,
        body=json.dumps(ticket),
        properties=pika.BasicProperties(
            delivery_mode=2,   # make message persistent (survives broker restart)
            content_type="application/json",
        ),
    )

    connection.close()
    print(f"📨 Ticket published to [{queue}]: {ticket['complaint_text'][:60]}...")
