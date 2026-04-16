"""
multi_agent.py — LangGraph pipeline from the original repo, upgraded with:
  - confidence_score node  (new)
  - conditional escalation edge  (new)
  - slack_user_id / slack_channel carried through state  (new)
  - jira_ticket_id written back into state after Jira creation  (new)

All original agent nodes (sentiment, severity, credibility, priority,
category, rag, resolution) are kept as-is from the source repo.
"""

import os
from dotenv import load_dotenv
from typing import TypedDict, List, Optional

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import OllamaLLM
from langgraph.graph import StateGraph, END

from database import save_complaint
from jira_client import create_jira_ticket
from slack_notifier import notify_user
from config import OLLAMA_MODEL, CONFIDENCE_THRESHOLD

load_dotenv()

# ── State ──────────────────────────────────────────────────────────────────────

class GraphState(TypedDict):
    complaint_text:   str
    sentiment:        str
    severity:         str
    credibility:      str
    priority:         str
    category:         str
    resolution:       str
    context_docs:     List[str]
    confidence_score: float
    escalated:        bool
    jira_ticket_id:   Optional[str]
    slack_user_id:    Optional[str]
    slack_channel:    Optional[str]

# ── Models ─────────────────────────────────────────────────────────────────────

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
)
vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=embedding_model,
)
retriever = vectorstore.as_retriever()
llm = OllamaLLM(model=OLLAMA_MODEL)

# ── Original nodes (unchanged from source repo) ────────────────────────────────

def rag_node(state: GraphState):
    docs = retriever.invoke(state["complaint_text"])
    return {"context_docs": [doc.page_content for doc in docs]}


def severity_node(state: GraphState):
    prompt = ChatPromptTemplate.from_template(
        "Classify severity of the complaint into one of: critical, high, medium, low.\n"
        "Complaint: {text}\nReturn only ONE word."
    )
    result = (prompt | llm | StrOutputParser()).invoke({"text": state["complaint_text"]})
    return {"severity": result.strip().lower()}


def credibility_node(state: GraphState):
    prompt = ChatPromptTemplate.from_template(
        "Determine whether the complaint language is exaggerated.\n"
        "Allowed outputs (return EXACTLY one): factual | mildly exaggerated | highly exaggerated\n"
        "Rules: Output only ONE phrase. No punctuation. No explanation.\n"
        "Complaint:\n{complaint}"
    )
    result = (prompt | llm | StrOutputParser()).invoke({"complaint": state["complaint_text"]})
    result = result.strip().lower()
    if "highly" in result:
        return {"credibility": "highly exaggerated"}
    if "mildly" in result:
        return {"credibility": "mildly exaggerated"}
    return {"credibility": "factual"}


def sentiment_node(state: GraphState):
    prompt = ChatPromptTemplate.from_template(
        "Determine the sentiment. Allowed: positive | neutral | negative\n"
        "Return ONE word. No punctuation.\nComplaint:\n{text}"
    )
    result = (prompt | llm | StrOutputParser()).invoke({"text": state["complaint_text"]})
    result = result.strip().lower()
    if "positive" in result:
        return {"sentiment": "positive"}
    if "neutral" in result:
        return {"sentiment": "neutral"}
    return {"sentiment": "negative"}


def priority_node(state: GraphState):
    severity = state.get("severity", "low")
    credibility = state.get("credibility", "factual")
    if severity == "critical":
        return {"priority": "critical"}
    if severity == "high" and credibility != "highly exaggerated":
        return {"priority": "high"}
    if severity == "medium":
        return {"priority": "medium"}
    return {"priority": "low"}


def category_node(state: GraphState):
    prompt = ChatPromptTemplate.from_template(
        "Select ONE category from: Roads, Electricity, Water, Sanitation, Healthcare, Law & Order\n"
        "Complaint: {text}\nReturn ONLY the category name."
    )
    raw = (prompt | llm | StrOutputParser()).invoke({"text": state["complaint_text"]}).strip()
    allowed = ["Roads", "Electricity", "Water", "Sanitation", "Healthcare", "Law & Order"]
    for a in allowed:
        if a.lower() in raw.lower():
            return {"category": a}
    return {"category": "Other"}


def resolution_node(state: GraphState):
    prompt = ChatPromptTemplate.from_template(
        "You are an automated support resolution engine.\n"
        "Output a VALID JSON object with EXACTLY these keys:\n"
        '{{"summary": string, "immediate_actions": array of 2-4 strings, '
        '"responsible_department": string, "sla_hours": number}}\n'
        "Rules: Raw JSON only. No markdown. No extra keys.\n"
        "Complaint:\n{complaint}\nRetrieved Context:\n{context}"
    )
    context = "\n".join(state["context_docs"][:3])
    resolution = (prompt | llm | StrOutputParser()).invoke({
        "complaint": state["complaint_text"],
        "context": context,
    })
    return {"resolution": resolution}

# ── New node: confidence scoring ───────────────────────────────────────────────

def confidence_node(state: GraphState):
    """
    Scores how confident the pipeline is in its resolution (0.0 – 1.0).
    Simple heuristic: penalise highly exaggerated credibility, low severity,
    and missing context docs. Can be replaced with an LLM-based scorer later.
    """
    score = 1.0

    if state.get("credibility") == "highly exaggerated":
        score -= 0.3
    elif state.get("credibility") == "mildly exaggerated":
        score -= 0.1

    if not state.get("context_docs"):
        score -= 0.2   # no RAG context found

    if state.get("severity") == "critical":
        score -= 0.15  # critical issues warrant human review

    score = max(0.0, round(score, 2))
    return {"confidence_score": score}

# ── New node: escalation decision ─────────────────────────────────────────────

def escalation_router(state: GraphState) -> str:
    """Conditional edge: route to auto-resolve or escalate."""
    if state["confidence_score"] >= CONFIDENCE_THRESHOLD:
        return "auto_resolve"
    return "escalate"


def auto_resolve_node(state: GraphState):
    """High-confidence path: create Jira ticket, mark resolved, notify user."""
    jira_id = create_jira_ticket(
        summary=f"[L1-AUTO] {state['category']} — {state['priority'].upper()}",
        description=state["complaint_text"],
        priority=state["priority"],
        resolution=state["resolution"],
    )
    row_id = save_complaint(
        complaint_text=state["complaint_text"],
        sentiment=state["sentiment"],
        severity=state["severity"],
        credibility=state["credibility"],
        category=state["category"],
        priority=state["priority"],
        resolution=state["resolution"],
        confidence_score=state["confidence_score"],
        escalated=False,
        jira_ticket_id=jira_id,
        slack_user_id=state.get("slack_user_id"),
        slack_channel=state.get("slack_channel"),
    )
    notify_user(
        channel=state.get("slack_channel"),
        user_id=state.get("slack_user_id"),
        message=(
            f"✅ *Ticket auto-resolved* (#{row_id})\n"
            f"*Category:* {state['category']} | *Priority:* {state['priority']}\n"
            f"*Jira:* {jira_id}\n"
            f"*Resolution summary:* {state['resolution'][:300]}..."
        ),
    )
    return {"escalated": False, "jira_ticket_id": jira_id}


def escalate_node(state: GraphState):
    """Low-confidence path: create Jira ticket flagged for human review."""
    jira_id = create_jira_ticket(
        summary=f"[L1-ESCALATED] {state['category']} — {state['priority'].upper()}",
        description=state["complaint_text"],
        priority=state["priority"],
        resolution=state["resolution"],
        escalated=True,
    )
    row_id = save_complaint(
        complaint_text=state["complaint_text"],
        sentiment=state["sentiment"],
        severity=state["severity"],
        credibility=state["credibility"],
        category=state["category"],
        priority=state["priority"],
        resolution=state["resolution"],
        confidence_score=state["confidence_score"],
        escalated=True,
        jira_ticket_id=jira_id,
        slack_user_id=state.get("slack_user_id"),
        slack_channel=state.get("slack_channel"),
    )
    notify_user(
        channel=state.get("slack_channel"),
        user_id=state.get("slack_user_id"),
        message=(
            f"⚠️ *Ticket escalated to human agent* (#{row_id})\n"
            f"*Category:* {state['category']} | *Priority:* {state['priority']}\n"
            f"*Jira:* {jira_id}\n"
            f"Our team will review and get back to you shortly."
        ),
    )
    return {"escalated": True, "jira_ticket_id": jira_id}

# ── Graph assembly ─────────────────────────────────────────────────────────────

workflow = StateGraph(GraphState)

workflow.add_node("sentiment_analysis",     sentiment_node)
workflow.add_node("severity_assessment",    severity_node)
workflow.add_node("credibility_assessment", credibility_node)
workflow.add_node("priority_determination", priority_node)
workflow.add_node("category_classification",category_node)
workflow.add_node("rag_retrieval",          rag_node)
workflow.add_node("resolution_generation",  resolution_node)
workflow.add_node("confidence_scoring",     confidence_node)   # NEW
workflow.add_node("auto_resolve",           auto_resolve_node) # NEW
workflow.add_node("escalate",               escalate_node)     # NEW

workflow.set_entry_point("sentiment_analysis")
workflow.add_edge("sentiment_analysis",      "severity_assessment")
workflow.add_edge("severity_assessment",     "credibility_assessment")
workflow.add_edge("credibility_assessment",  "priority_determination")
workflow.add_edge("priority_determination",  "category_classification")
workflow.add_edge("category_classification", "rag_retrieval")
workflow.add_edge("rag_retrieval",           "resolution_generation")
workflow.add_edge("resolution_generation",   "confidence_scoring")   # NEW

# Conditional branch based on confidence score
workflow.add_conditional_edges(
    "confidence_scoring",
    escalation_router,
    {
        "auto_resolve": "auto_resolve",
        "escalate":     "escalate",
    },
)

workflow.add_edge("auto_resolve", END)
workflow.add_edge("escalate",     END)

app = workflow.compile()
