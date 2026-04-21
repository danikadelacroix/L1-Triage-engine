# Autonomous L1 Support Engine

An autonomous Level-1 IT & HR support engine for enterprise helpdesks. Employees raise tickets via **Slack** — the engine classifies, retrieves context from the company knowledge base, generates a resolution, scores its own confidence, and either auto-resolves by creating a **Jira ticket** or escalates to a human agent. All processing is fully asynchronous via **RabbitMQ**.

---

## Architecture

```
Employee (Slack)
      │  /raise-ticket  OR  @mention bot
      ▼
┌──────────────────┐
│  FastAPI          │  Verifies Slack signature, acks in <3s
└────────┬─────────┘
         ▼
┌──────────────────┐
│  RabbitMQ         │  priority_tickets_queue / tickets_queue
└────────┬─────────┘
         ▼
┌─────────────────────────────────────────┐
│  Worker — LangGraph Multi-Agent Pipeline │
│                                         │
│  Sentiment → Severity → Credibility     │
│  → Priority → Category → RAG Retrieval  │
│  → Resolution → Confidence Scoring      │
│                                         │
│       confidence ≥ 0.7?                 │
│        ↙              ↘                 │
│  Auto-Resolve       Escalate            │
│  Jira ticket    Jira ticket (flagged)   │
│  + Slack reply  + Slack reply           │
└─────────────────────────────────────────┘
         ▼
┌──────────────────┐
│  PostgreSQL       │  Full audit log per ticket
└──────────────────┘
```
## Key Features

- 🔁 Asynchronous ticket processing via RabbitMQ
- 🧠 Multi-agent reasoning pipeline (LangGraph)
- 📚 RAG-based knowledge retrieval (ChromaDB)
- 🎯 Confidence-based auto-resolution vs escalation
- 🔔 Slack integration for real-time interaction
- 🎟️ Jira integration for ticket creation

---

## Tech Stack

| Layer              | Technology                                |
| ------------------ | ----------------------------------------- |
| Interface          | Slack (Slash Commands + Event API)        |
| API Server         | FastAPI + Uvicorn                         |
| Message Queue      | RabbitMQ (pika)                           |
| AI Orchestration   | LangGraph                                 |
| LLM                | Ollama — Mistral 7B                       |
| RAG / Vector Store | ChromaDB + HuggingFace `all-MiniLM-L6-v2` |
| Ticketing          | Jira REST API v3                          |
| Database           | PostgreSQL                                |
| Infrastructure     | Docker + Docker Compose                   |

---

## Setup

### Prerequisites
- Python 3.10+, Docker, [Ollama](https://ollama.ai), [ngrok](https://ngrok.com)
- A Slack App and (optionally) a Jira account with API token

### Steps

```bash
# 1. Install dependencies
git clone https://github.com/your-username/l1-support-engine.git
cd l1-support-engine
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt

# 2. Pull the LLM
ollama serve && ollama pull mistral

# 3. Configure environment
cp .env.example .env   # fill in Slack, Jira, DB credentials

# 4. Start infrastructure
docker-compose up -d   # RabbitMQ UI → localhost:15672 | PostgreSQL → 5432

# 5. Prepare knowledge base
pip install docx2txt && mkdir kb_docs
python -c "import docx2txt; open('kb_docs/kb.txt','w').write(docx2txt.process('your_kb.docx'))"

# 6. First-time setup (DB schema + KB ingestion + smoke tests)
python first_script.py

# 7. Run (three terminals)
uvicorn app:app --reload --port 8000
python worker.py
ngrok http 8000
```

---

## Slack App Setup

1. [Create a Slack App](https://api.slack.com/apps) → **From scratch**
2. **OAuth & Permissions** — add bot scopes: `chat:write`, `commands`, `app_mentions:read`, `im:history`, `im:write`
3. **Slash Commands** — create `/raise-ticket`, request URL: `https://<ngrok>/slack/commands`
4. **Event Subscriptions** — enable, set URL: `https://<ngrok>/slack/events`, subscribe to `app_mention` and `message.im`
5. Install to workspace, copy Bot Token + Signing Secret to `.env`

---

> Jira is optional — if `JIRA_BASE_URL` is unset, the engine runs in mock mode with a fake ticket ID.

---

## Live Demo

Experience the AI triage system in action and join the Slack workspace:  
https://join.slack.com/t/newworkspace-jjo8297/shared_invite/zt-3wa6fl7gw-WInnFFWbgMAZxfLpoun_gw  

> Note: The backend is hosted locally to optimize costs. If the bot is unresponsive, feel free to reach out, I can spin up the server for a live demo.



> Built by **Anushka Rajput**, 3rd Year Computer Science Student, IET Lucknow  
Built as a project to explore autonomous AI agents, RAG systems, and real-world LLM applications in enterprise workflows.