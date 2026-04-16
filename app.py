"""
app.py — FastAPI server replacing the original Streamlit app.

Exposes two endpoints:
  POST /slack/events   — receives Slack event subscriptions (mentions, DMs)
  POST /slack/commands — receives /raise-ticket slash command

On receiving a ticket, it immediately acks Slack (within 3s requirement)
and publishes the ticket to RabbitMQ for async processing.
"""

import hmac
import hashlib
import time
import json

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from producer import publish_ticket
from slack_notifier import notify_user
from config import SLACK_SIGNING_SECRET

app = FastAPI(title="Autonomous L1 Support Engine")


# ── Slack signature verification ───────────────────────────────────────────────

def verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """
    Verifies the request actually came from Slack using HMAC-SHA256.
    Prevents anyone else from posting to your endpoint.
    """
    if abs(time.time() - float(timestamp)) > 60 * 5:
        return False  # Replay attack guard

    sig_basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"
    computed = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Slack slash command: /raise-ticket ────────────────────────────────────────

@app.post("/slack/commands")
async def slack_command(request: Request, background_tasks: BackgroundTasks):
    """
    User types: /raise-ticket My internet has been down for 3 days.
    Slack posts a form-encoded payload to this endpoint.
    We ack immediately, then publish to queue in the background.
    """
    body_bytes = await request.body()
    timestamp  = request.headers.get("X-Slack-Request-Timestamp", "")
    signature  = request.headers.get("X-Slack-Signature", "")

    if not verify_slack_signature(body_bytes, timestamp, signature):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    form = await request.form()
    complaint_text = form.get("text", "").strip()
    slack_user_id  = form.get("user_id", "")
    slack_channel  = form.get("channel_id", "")

    if not complaint_text:
        return JSONResponse(content={
            "response_type": "ephemeral",
            "text": "❌ Please provide a description after /raise-ticket"
        })

    ticket = {
        "complaint_text": complaint_text,
        "slack_user_id":  slack_user_id,
        "slack_channel":  slack_channel,
    }

    # Publish in background so Slack gets a response within 3 seconds
    background_tasks.add_task(publish_ticket, ticket)

    # Immediate ack to Slack
    return JSONResponse(content={
        "response_type": "ephemeral",
        "text": (
            "🎫 *Ticket received!* Our AI is analysing your issue.\n"
            "You'll get a resolution or escalation update shortly."
        ),
    })


# ── Slack Event Subscriptions (bot mentions / DMs) ────────────────────────────

@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """
    Handles Slack Event API payloads.
    Supports:
      - url_verification challenge (one-time during Slack app setup)
      - app_mention: user @mentions the bot in a channel
      - message.im: user DMs the bot directly
    """
    body_bytes = await request.body()
    timestamp  = request.headers.get("X-Slack-Request-Timestamp", "")
    signature  = request.headers.get("X-Slack-Signature", "")

    if not verify_slack_signature(body_bytes, timestamp, signature):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")

    payload = json.loads(body_bytes)

    # Slack sends a challenge during app setup — must echo it back
    if payload.get("type") == "url_verification":
        return JSONResponse(content={"challenge": payload["challenge"]})

    event = payload.get("event", {})
    event_type = event.get("type", "")

    # Ignore bot's own messages to prevent loops
    if event.get("bot_id"):
        return JSONResponse(content={"ok": True})

    if event_type in ("app_mention", "message"):
        complaint_text = event.get("text", "").strip()
        # Strip the bot mention prefix if present (e.g. "<@U12345> my issue...")
        if complaint_text.startswith("<@"):
            complaint_text = complaint_text.split(">", 1)[-1].strip()

        if not complaint_text:
            return JSONResponse(content={"ok": True})

        ticket = {
            "complaint_text": complaint_text,
            "slack_user_id":  event.get("user"),
            "slack_channel":  event.get("channel"),
        }

        background_tasks.add_task(publish_ticket, ticket)

    return JSONResponse(content={"ok": True})
