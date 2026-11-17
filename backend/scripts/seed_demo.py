"""Seed a demo workspace ("Northwind") with documents, two meetings and a few decisions.

    python scripts/seed_demo.py you@company.com

Runs the real API in-process against whatever DATABASE_URL / providers your .env configures, so it exercises
the full ingestion + extraction pipeline. In AUTH_MODE=dev, sign in with the same email to see it.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import dev_user_id  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

today = date.today()

DOCS = {
    "Pricing Policy.md": """# Pricing Policy

The Pro plan costs $49 per seat per month. Annual billing receives a 20% discount.
The Team plan costs $99 per seat per month and includes SSO and audit logs.

Refunds are available within 30 days of purchase, for annual plans only.
Discounts above 30% require approval from the CFO (Dana Wright).
""",
    "Engineering Onboarding Guide.md": """# Engineering Onboarding

Every new engineer gets an onboarding buddy for their first two weeks.
Day 1: laptop setup, GitHub access and a walkthrough of the monorepo with your buddy.
Week 1: ship a small bug fix to production. Deploys go out through the main CI pipeline every weekday at 3pm.
On-call: engineers join the on-call rotation after 60 days. The rotation is weekly and hand-off is Monday at 10am.
Ask questions in #eng-help. The engineering manager is Marcus Lee.
""",
    "Security Policy 2024.md": """# Security Policy

All laptops must use full disk encryption.
Production database backups run every 24 hours and are retained for 30 days.
Access to production requires hardware security keys.
""",
    "Infrastructure Runbook.md": """# Infrastructure Runbook

Production database backups run every 6 hours and are retained for 90 days.
Failover to the replica region is manual and takes about 15 minutes.
""",
}

SYNC = f"""Weekly product sync
Attendees: Priya, Marcus, Dana, Leo

Decisions:
- Move the public launch to {(today + timedelta(days=40)).strftime('%B %d')} because QA needs another sprint
- Use Postgres for analytics instead of BigQuery, approved by Marcus
- Offer a free tier for the self-serve plan

Action items:
- Leo to update the launch plan by Friday
- @Priya draft the pricing FAQ (due {(today - timedelta(days=2)).isoformat()})
- Marcus will migrate the analytics jobs next week
- Write the release notes

Open questions:
- Who owns the customer data migration?
- Do enterprise customers need a separate SLA?
"""

PLANNING = """Leo: Quick one on pricing. We decided not to offer a free tier for the self-serve plan since support costs are too high.
Dana: Agreed. I'll send the revised pricing deck tomorrow.
Priya: Is the SOC 2 audit timeline still unclear?
Marcus: Nobody knows yet. Let's go with the vendor Vanta for compliance automation.
"""


def main(email: str) -> None:
    s = get_settings()
    if s.auth_mode != "dev":
        raise SystemExit("seed_demo uses dev tokens: run it with AUTH_MODE=dev")
    h = {"Authorization": f"Bearer dev:{email}"}
    with TestClient(app) as c:
        ws = c.post("/api/workspaces", json={"name": "Northwind"}, headers=h).json()["id"]
        launch = c.post(f"/api/workspaces/{ws}/projects", json={"name": "Launch", "description": "Public launch"}, headers=h).json()
        for name, body in DOCS.items():
            c.post(f"/api/workspaces/{ws}/documents", files={"file": (name, body.encode())}, headers=h)
        c.post(
            f"/api/workspaces/{ws}/meetings",
            data={"title": "Weekly product sync", "held_on": (today - timedelta(days=6)).isoformat(), "text": SYNC, "project_id": launch["id"]},
            headers=h,
        )
        c.post(
            f"/api/workspaces/{ws}/meetings",
            data={"title": "Pricing check-in", "held_on": (today - timedelta(days=1)).isoformat(), "text": PLANNING, "project_id": launch["id"]},
            headers=h,
        )
        c.post(
            f"/api/workspaces/{ws}/decisions",
            json={"title": "Hire a second product designer in Q1", "rationale": "Design is the bottleneck for launch work", "approved_by": "Dana"},
            headers=h,
        )
        c.post(f"/api/workspaces/{ws}/gaps/scan", headers=h)
        print(f"Seeded workspace {ws} for {email} (user id {dev_user_id(email)})")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo@northwind.test")
