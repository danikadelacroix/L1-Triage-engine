"""
slack_notifier.py — sends messages back to Slack after ticket processing.

Used by both auto_resolve_node and escalate_node in multi_agent.py.
"""

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from config import SLACK_BOT_TOKEN

client = WebClient(token=SLACK_BOT_TOKEN)


def notify_user(channel: str, user_id: str, message: str):
    """
    Posts a message to the channel where the ticket was raised.
    Mentions the user so they get a notification.
    """
    if not channel:
        print("⚠️  No Slack channel provided — skipping notification.")
        return

    try:
        full_message = f"<@{user_id}> {message}" if user_id else message
        client.chat_postMessage(
            channel=channel,
            text=full_message,
            mrkdwn=True,
        )
        print(f"📣 Slack notification sent to {channel}")
    except SlackApiError as e:
        print(f"❌ Slack notification failed: {e.response['error']}")
