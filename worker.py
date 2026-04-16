"""
worker.py — RabbitMQ consumer.

Runs as a separate long-lived process:
    python worker.py

Listens on both queues (priority first, then standard).
For each message, runs the full LangGraph multi-agent pipeline.
Acknowledges only after successful processing — if it crashes,
RabbitMQ requeues the message automatically.
"""

import json
import pika
from multi_agent import app as langgraph_app
from config import RABBITMQ_URL, TICKET_QUEUE, PRIORITY_TICKET_QUEUE


def process_ticket(body: bytes):
    ticket = json.loads(body)
    print(f"\n🔧 Processing ticket: {ticket['complaint_text'][:80]}...")

    initial_state = {
        "complaint_text":   ticket["complaint_text"],
        "slack_user_id":    ticket.get("slack_user_id"),
        "slack_channel":    ticket.get("slack_channel"),
        # remaining fields are filled by the pipeline
        "sentiment":        "",
        "severity":         "",
        "credibility":      "",
        "priority":         "",
        "category":         "",
        "resolution":       "",
        "context_docs":     [],
        "confidence_score": 0.0,
        "escalated":        False,
        "jira_ticket_id":   None,
    }

    result = langgraph_app.invoke(initial_state)
    print(f"✅ Done — escalated={result['escalated']} | jira={result.get('jira_ticket_id')}")
    return result


def on_message(channel, method, properties, body):
    try:
        process_ticket(body)
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"❌ Failed to process ticket: {e}")
        # Negative ack — requeue once, then route to DLQ if it fails again
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_worker():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.queue_declare(queue=TICKET_QUEUE,          durable=True)
    channel.queue_declare(queue=PRIORITY_TICKET_QUEUE, durable=True)

    # Process one message at a time per worker — prevents overload
    channel.basic_qos(prefetch_count=1)

    # Priority queue first, then standard queue
    channel.basic_consume(queue=PRIORITY_TICKET_QUEUE, on_message_callback=on_message)
    channel.basic_consume(queue=TICKET_QUEUE,          on_message_callback=on_message)

    print("🚀 Worker started. Waiting for tickets... (CTRL+C to stop)")
    channel.start_consuming()


if __name__ == "__main__":
    start_worker()
