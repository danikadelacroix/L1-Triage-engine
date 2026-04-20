"""
first_script.py — one-time setup script for the NovaTech L1 Support Engine.

Run this ONCE before starting the application to:
  1. Ingest the NovaTech KB (novatech_kb.docx or novatech_kb.txt) into ChromaDB
  2. Seed the PostgreSQL database schema
  3. Smoke-test the LLM with an IT support-flavoured sentiment check

Usage:
    python first_script.py
"""

import json
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from database import init_db
from rag_pipeline import ingest_documents
from config import OLLAMA_MODEL

llm = OllamaLLM(model=OLLAMA_MODEL)


# ── 1. Seed the database ───────────────────────────────────────────────────────

def setup_database():
    print("📦 Initialising PostgreSQL schema...")
    init_db()
    print("✅ Database ready.\n")


# ── 2. Ingest NovaTech KB into ChromaDB ───────────────────────────────────────

def setup_knowledge_base():
    print("📚 Ingesting NovaTech Knowledge Base into ChromaDB...")
    ingest_documents()
    print("✅ Knowledge base ingested.\n")


# ── 3. Smoke-test: IT support sentiment analysis ──────────────────────────────

def test_it_support_sentiment():
    """
    Tests the LLM's sentiment detection on IT/HR helpdesk language.

    Unlike a government grievance portal (where complaints are civic frustration),
    enterprise IT support tickets have a different emotional register:
      - Urgency / blocked work  → negative
      - Informational queries   → neutral
      - Resolved / thank you    → positive

    The prompt is tuned for this professional, workplace context.
    """

    test_tickets = [
        # negative — blocked from working
        "I cannot access my laptop since this morning. My screen just shows a black "
        "screen after login. I have a client call in 2 hours and this is urgent.",

        # neutral — informational / how-to
        "Can you tell me how many days of privileged leave I have left for this year "
        "and what the process is to apply for them in Workday?",

        # negative — payroll issue
        "My salary for March was short by Rs. 4,200. I checked my payslip and the "
        "internet reimbursement of Rs. 1,000 and one day's attendance deduction seem "
        "incorrect. Please look into this.",

        # positive — appreciative follow-up
        "Thank you — the VPN issue has been resolved. Everything is working fine now.",

        # negative — escalation frustration
        "This is the third time I'm raising a ticket about the same issue. My AWS "
        "console access was supposed to be provisioned 10 days ago and nothing has "
        "happened. My manager has approved it twice already.",
    ]

    prompt = ChatPromptTemplate.from_template(
        """
You are an IT/HR helpdesk sentiment classifier for an enterprise support system.

Classify the sentiment of the support ticket below. Consider the context:
- "negative" means the employee is frustrated, blocked, urgently impacted, or experiencing a service failure
- "neutral" means an informational query, how-to question, or general request with no emotional distress
- "positive" means a thank you, confirmation, or satisfied follow-up

Allowed outputs (return EXACTLY one JSON object and nothing else):
{{"sentiment": "positive" | "neutral" | "negative", "reason": "<one sentence>"}}

Support Ticket:
{ticket}
        """
    )

    chain = prompt | llm | StrOutputParser()

    print("🧪 Smoke-testing IT support sentiment classifier...\n")
    print("─" * 60)

    for i, ticket in enumerate(test_tickets, 1):
        result = chain.invoke({"ticket": ticket})
        try:
            parsed = json.loads(result.strip())
            sentiment = parsed.get("sentiment", "unknown")
            reason = parsed.get("reason", "")
            icon = {"positive": "🟢", "neutral": "🟡", "negative": "🔴"}.get(sentiment, "⚪")
            print(f"Ticket {i}: {icon} {sentiment.upper()}")
            print(f"  Ticket: {ticket[:80]}...")
            print(f"  Reason: {reason}")
        except json.JSONDecodeError:
            print(f"Ticket {i}: ⚠️  Raw output (JSON parse failed): {result.strip()}")
        print()

    print("─" * 60)
    print("✅ Sentiment smoke-test complete.\n")


# ── 4. Smoke-test: category classification for IT/HR domains ─────────────────

def test_category_classification():
    """
    Tests that the LLM correctly maps IT/HR tickets to the categories
    used in our pipeline. These map to the sections in the NovaTech KB.
    """

    test_cases = [
        ("My laptop screen has dead pixels and is cracking at the hinge.", "Hardware"),
        ("I can't log in to the VPN from home. Getting an MFA error.", "Network / VPN"),
        ("I need access to the AWS production console for my new project.", "Access Management"),
        ("When does the investment declaration window close this year?", "HR / Payroll"),
        ("My manager is assigning me to weekend shifts without compensatory off.", "Grievance"),
        ("How do I install PyCharm? It's not showing in the software portal.", "Software"),
    ]

    prompt = ChatPromptTemplate.from_template(
        """
Classify this IT/HR support ticket into exactly ONE of these categories:
Hardware | Software | Network / VPN | Access Management | HR / Payroll | Grievance | Security | Other

Return ONLY the category name.

Ticket: {ticket}
        """
    )

    chain = prompt | llm | StrOutputParser()

    print("🧪 Smoke-testing category classifier...\n")
    print("─" * 60)

    for ticket, expected in test_cases:
        result = chain.invoke({"ticket": ticket}).strip()
        match = "✅" if expected.lower() in result.lower() else "⚠️ "
        print(f"{match} Expected: {expected:<20} Got: {result}")
        print(f"   Ticket: {ticket[:80]}")
        print()

    print("─" * 60)
    print("✅ Category smoke-test complete.\n")


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  NovaTech L1 Support Engine — First-Run Setup")
    print("=" * 60)
    print()

    setup_database()
    setup_knowledge_base()
    test_it_support_sentiment()
    test_category_classification()

    print("🚀 Setup complete. You can now run:")
    print("   docker-compose up -d   (start RabbitMQ + PostgreSQL)")
    print("   uvicorn app:app --reload  (start FastAPI server)")
    print("   python worker.py          (start RabbitMQ worker)")
