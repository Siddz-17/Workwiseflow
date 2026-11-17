from datetime import date, timedelta

from app.services.dates import resolve_due
from app.services.llm import LocalProvider

NOTES = """Weekly product sync
Attendees: Alice, Bob, Priya

Decisions:
- Move the launch to March 3 because QA needs another sprint
- Use Postgres for analytics instead of BigQuery

Action items:
- Bob to update the launch plan by Friday
- @Priya draft the pricing FAQ (due 2026-11-25)
- Write release notes

Open questions:
- Who owns the customer migration?
"""

TRANSCRIPT = """Alice: Thanks for joining. We decided to drop the free tier since it costs too much to support.
Bob: I'll send the churn analysis tomorrow.
Priya: Is the SOC 2 audit still unclear on timing?
"""


def test_local_extraction_from_notes():
    ex = LocalProvider().extract_meeting(NOTES, date(2026, 11, 18), [])
    assert ex.attendees == ["Alice", "Bob", "Priya"]
    titles = [d["title"] for d in ex.decisions]
    assert titles[0].startswith("Move the launch to March 3") and ex.decisions[0]["rationale"].startswith("QA needs")
    assert any("Postgres" in t for t in titles)
    by_task = {a["task"]: a for a in ex.action_items}
    bob = next(a for a in ex.action_items if a["owner"] == "Bob")
    assert bob["due_date"] == "2026-11-20"  # Friday after Wed 18 Nov
    priya = next(a for a in ex.action_items if a["owner"] == "Priya")
    assert priya["due_date"] == "2026-11-25"
    assert by_task["Write release notes"]["owner"] is None
    assert ex.open_questions == ["Who owns the customer migration?"]


def test_local_extraction_from_transcript():
    ex = LocalProvider().extract_meeting(TRANSCRIPT, date(2026, 11, 18), [])
    assert ex.decisions and "free tier" in ex.decisions[0]["title"] and ex.decisions[0]["approved_by"] == "Alice"
    assert ex.action_items[0]["owner"] == "Bob" and ex.action_items[0]["due_date"] == "2026-11-19"
    assert ex.open_questions


def test_resolve_due():
    ref = date(2026, 11, 18)  # Wednesday
    assert resolve_due("by friday", ref) == date(2026, 11, 20)
    assert resolve_due("by next week", ref) == date(2026, 11, 23)
    assert resolve_due("due Dec 3", ref) == date(2026, 12, 3)
    assert resolve_due("by 5 January", ref) == date(2027, 1, 5)
    assert resolve_due("end of month", ref) == date(2026, 11, 30)
    assert resolve_due("in 2 weeks", ref) == date(2026, 12, 2)
    assert resolve_due("update the marketing site", ref) is None


def test_meeting_upload_creates_records(client, alice, workspace):
    # Alice is a member, so "Alice" should map to her account.
    r = client.post(
        f"/api/workspaces/{workspace}/meetings",
        data={"title": "Product sync", "held_on": "2026-11-18", "text": NOTES},
        headers=alice,
    )
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    m = client.get(f"/api/workspaces/{workspace}/meetings/{mid}", headers=alice).json()
    assert m["status"] == "ready"
    assert len(m["decisions"]) == 2 and len(m["action_items"]) == 3 and len(m["open_questions"]) == 1

    # Meeting content is also searchable.
    ans = client.post(f"/api/workspaces/{workspace}/chat/ask", json={"question": "Why did the launch move?"}, headers=alice).json()
    assert ans["answer"]["answered"] and "QA" in ans["answer"]["content"]


def test_action_filters(client, alice, workspace):
    base = f"/api/workspaces/{workspace}/actions"
    past = (date.today() - timedelta(days=3)).isoformat()
    me = client.get("/api/me", headers=alice).json()["user"]["id"]
    client.post(base, json={"title": "Overdue thing", "due_on": past, "owner_user_id": me}, headers=alice)
    client.post(base, json={"title": "Orphan task"}, headers=alice)
    done = client.post(base, json={"title": "Done task", "due_on": past, "owner_name": "Bob"}, headers=alice).json()
    client.patch(f"{base}/{done['id']}", json={"status": "done"}, headers=alice)

    overdue = client.get(base, params={"overdue": True}, headers=alice).json()
    assert [a["title"] for a in overdue] == ["Overdue thing"] and overdue[0]["overdue"]
    assert [a["title"] for a in client.get(base, params={"unassigned": True}, headers=alice).json()] == ["Orphan task"]
    assert [a["title"] for a in client.get(base, params={"mine": True}, headers=alice).json()] == ["Overdue thing"]
    assert len(client.get(base, params={"status": "incomplete"}, headers=alice).json()) == 2

    ov = client.get(f"/api/workspaces/{workspace}/overview", headers=alice).json()
    assert ov["actions_open"] == 2 and ov["actions_overdue"] == 1 and ov["actions_unassigned"] == 1


def test_decision_tracker_search_and_supersede(client, alice, workspace):
    base = f"/api/workspaces/{workspace}/decisions"
    a = client.post(base, json={"title": "Use Stripe for billing", "rationale": "Best API", "approved_by": "Alice"}, headers=alice).json()
    b = client.post(base, json={"title": "Hire a second designer in Q1"}, headers=alice).json()
    hits = client.get(base, params={"q": "stripe billing"}, headers=alice).json()
    assert hits[0]["id"] == a["id"]
    c = client.post(base, json={"title": "Use Paddle for billing instead of Stripe"}, headers=alice).json()
    r = client.patch(f"{base}/{a['id']}", json={"superseded_by_id": c["id"]}, headers=alice).json()
    assert r["status"] == "superseded"
    active = client.get(base, params={"status": "active"}, headers=alice).json()
    assert {d["id"] for d in active} == {b["id"], c["id"]}
    confirmed = client.patch(f"{base}/{b['id']}", json={"confirm": True}, headers=alice).json()
    assert confirmed["last_confirmed_at"]


def test_conflicting_decisions_are_flagged(client, alice, workspace):
    base = f"/api/workspaces/{workspace}/decisions"
    client.post(base, json={"title": "Offer a free tier for the self-serve plan"}, headers=alice)
    client.post(base, json={"title": "Do not offer a free tier for the self-serve plan"}, headers=alice)
    gaps = client.get(f"/api/workspaces/{workspace}/gaps", headers=alice).json()
    assert len(gaps["conflicts"]) == 1 and gaps["conflicts"][0]["kind"] == "decision"
    cid = gaps["conflicts"][0]["id"]
    client.patch(f"/api/workspaces/{workspace}/conflicts/{cid}", json={"status": "resolved"}, headers=alice)
    assert client.get(f"/api/workspaces/{workspace}/gaps", headers=alice).json()["conflicts"] == []


def test_conflicting_documents_are_flagged_on_scan(client, alice, workspace):
    for name, body in [("sec-a.txt", b"Production database backups run every 24 hours and are kept for 30 days."),
                       ("sec-b.txt", b"Production database backups run every 6 hours and are kept for 90 days.")]:
        client.post(f"/api/workspaces/{workspace}/documents", files={"file": (name, body)}, headers=alice)
    r = client.post(f"/api/workspaces/{workspace}/gaps/scan", headers=alice).json()
    assert r["new_conflicts"] == 1
    c = client.get(f"/api/workspaces/{workspace}/gaps", headers=alice).json()["conflicts"][0]
    assert c["kind"] == "document" and "figures" in c["explanation"]
