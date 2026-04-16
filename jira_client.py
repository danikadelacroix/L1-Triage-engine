"""
jira_client.py — creates Jira issues via the Jira REST API v3.

Replaces the empty notify_officials_node stub from the original repo.
"""

import requests
from requests.auth import HTTPBasicAuth
from config import JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY

# Map our internal priority labels to Jira's priority names
PRIORITY_MAP = {
    "critical": "Highest",
    "high":     "High",
    "medium":   "Medium",
    "low":      "Low",
}


def create_jira_ticket(
    summary: str,
    description: str,
    priority: str = "medium",
    resolution: str = "",
    escalated: bool = False,
) -> str:
    """
    Creates a Jira issue and returns the issue key (e.g. "SUP-42").
    If Jira is not configured, returns a mock ID for local dev.
    """
    if not JIRA_BASE_URL or not JIRA_EMAIL or not JIRA_API_TOKEN:
        mock_id = f"SUP-MOCK-{hash(summary) % 9999}"
        print(f"⚠️  Jira not configured — mock ticket: {mock_id}")
        return mock_id

    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    labels = ["l1-support", "escalated" if escalated else "auto-resolved"]

    payload = {
        "fields": {
            "project":     {"key": JIRA_PROJECT_KEY},
            "summary":     summary,
            "description": {
                "type":    "doc",
                "version": 1,
                "content": [
                    {
                        "type":    "paragraph",
                        "content": [{"type": "text", "text": description}],
                    },
                    {
                        "type":    "paragraph",
                        "content": [{"type": "text", "text": f"\n\nAI Resolution:\n{resolution}"}],
                    },
                ],
            },
            "issuetype": {"name": "Support Request"},
            "priority":  {"name": PRIORITY_MAP.get(priority.lower(), "Medium")},
            "labels":    labels,
        }
    }

    response = requests.post(url, json=payload, headers=headers, auth=auth)

    if response.status_code == 201:
        issue_key = response.json()["key"]
        print(f"✅ Jira ticket created: {issue_key}")
        return issue_key
    else:
        print(f"❌ Jira API error {response.status_code}: {response.text}")
        return f"ERR-{response.status_code}"
