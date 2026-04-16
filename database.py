"""
database.py — upgraded from SQLite to PostgreSQL.
Schema mirrors the original but adds: slack_user_id, slack_channel,
jira_ticket_id, confidence_score, escalated flag.
"""

import psycopg2
import psycopg2.extras
from config import DATABASE_URL


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """Create complaints table if it doesn't exist."""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id                SERIAL PRIMARY KEY,
            complaint_text    TEXT NOT NULL,
            sentiment         TEXT,
            severity          TEXT,
            credibility       TEXT,
            category          TEXT,
            priority          TEXT,
            resolution        TEXT,
            confidence_score  FLOAT,
            escalated         BOOLEAN DEFAULT FALSE,
            jira_ticket_id    TEXT,
            slack_user_id     TEXT,
            slack_channel     TEXT,
            timestamp         TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()


def save_complaint(
    complaint_text,
    sentiment,
    severity,
    credibility,
    category,
    priority,
    resolution,
    confidence_score=None,
    escalated=False,
    jira_ticket_id=None,
    slack_user_id=None,
    slack_channel=None,
):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO complaints
            (complaint_text, sentiment, severity, credibility,
             category, priority, resolution, confidence_score,
             escalated, jira_ticket_id, slack_user_id, slack_channel)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (
        complaint_text, sentiment, severity, credibility,
        category, priority, resolution, confidence_score,
        escalated, jira_ticket_id, slack_user_id, slack_channel
    ))
    row_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return row_id


def get_all_complaints():
    conn = get_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM complaints ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


if __name__ == "__main__":
    init_db()
    print("✅ PostgreSQL table initialised.")
