from producer import publish_ticket

ticket = {
    "complaint_text": "My March salary is short by Rs 4000!",
    "slack_user_id": "U-TEST",
    "slack_channel": "C-TEST"
}

# Publish it directly to the queue
publish_ticket(ticket, high_priority=True)