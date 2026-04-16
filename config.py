import os
from dotenv import load_dotenv

load_dotenv()

# Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# RabbitMQ
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
TICKET_QUEUE = "tickets_queue"
PRIORITY_TICKET_QUEUE = "priority_tickets_queue"

# PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/l1support")

# Jira
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")          # e.g. https://yourcompany.atlassian.net
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "SUP")

# LLM
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

# Confidence threshold — below this score, ticket escalates to human
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
