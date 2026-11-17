import io

import docx
import pymupdf as fitz

from conftest import auth

PRICING = """Pricing Policy

Our Pro plan costs 49 dollars per seat per month. Annual billing gets a 20 percent discount.

Refunds are available within 30 days of purchase for annual plans only.
"""


def upload(client, ws, headers, name, data, **form):
    r = client.post(f"/api/workspaces/{ws}/documents", files={"file": (name, data)}, data=form, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def make_pdf(text: str) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    return pdf.tobytes()


def make_docx(text: str) -> bytes:
    d = docx.Document()
    for line in text.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def test_upload_txt_is_ingested(client, alice, workspace):
    doc = upload(client, workspace, alice, "pricing.txt", PRICING.encode())
    detail = client.get(f"/api/workspaces/{workspace}/documents/{doc['id']}", headers=alice).json()
    assert detail["status"] == "ready"
    assert detail["chunks"] and "49 dollars" in " ".join(c["content"] for c in detail["chunks"])
    raw = client.get(f"/api/workspaces/{workspace}/documents/{doc['id']}/file", headers=alice)
    assert raw.content == PRICING.encode()


def test_pdf_and_docx_parsing_with_pages(client, alice, workspace):
    pdf = upload(client, workspace, alice, "security.pdf", make_pdf("All laptops must use full disk encryption."))
    dx = upload(client, workspace, alice, "onboarding.docx", make_docx("New hires get a buddy for their first two weeks."))
    pd = client.get(f"/api/workspaces/{workspace}/documents/{pdf['id']}", headers=alice).json()
    assert pd["status"] == "ready" and pd["chunks"][0]["page"] == 1
    dd = client.get(f"/api/workspaces/{workspace}/documents/{dx['id']}", headers=alice).json()
    assert dd["status"] == "ready" and "buddy" in dd["chunks"][0]["content"]


def test_unsupported_type_rejected(client, alice, workspace):
    r = client.post(f"/api/workspaces/{workspace}/documents", files={"file": ("x.exe", b"MZ")}, headers=alice)
    assert r.status_code == 415


def test_ask_returns_cited_answer_and_persists_thread(client, alice, workspace):
    doc = upload(client, workspace, alice, "pricing.txt", PRICING.encode())
    r = client.post(f"/api/workspaces/{workspace}/chat/ask", json={"question": "How much does the Pro plan cost?"}, headers=alice)
    body = r.json()
    assert body["answer"]["answered"] is True
    assert "49" in body["answer"]["content"]
    cites = body["answer"]["citations"]
    assert cites and cites[0]["document_id"] == doc["id"] and "[1]" in body["answer"]["content"]

    tid = body["thread"]["id"]
    r2 = client.post(
        f"/api/workspaces/{workspace}/chat/ask", json={"question": "What about refunds?", "thread_id": tid}, headers=alice
    )
    assert "30 days" in r2.json()["answer"]["content"]
    thread = client.get(f"/api/workspaces/{workspace}/chat/threads/{tid}", headers=alice).json()
    assert len(thread["messages"]) == 4


def test_threads_are_private_to_their_user(client, alice, bob, workspace):
    client.post(f"/api/workspaces/{workspace}/invites", json={"email": "bob@acme.test"}, headers=alice)
    r = client.post(f"/api/workspaces/{workspace}/chat/ask", json={"question": "hello there team"}, headers=alice)
    tid = r.json()["thread"]["id"]
    assert client.get(f"/api/workspaces/{workspace}/chat/threads/{tid}", headers=bob).status_code == 404


def test_unanswerable_question_becomes_a_gap(client, alice, workspace):
    upload(client, workspace, alice, "pricing.txt", PRICING.encode())
    for _ in range(2):
        r = client.post(
            f"/api/workspaces/{workspace}/chat/ask", json={"question": "Who is our Kubernetes vendor?"}, headers=alice
        )
        assert r.json()["answer"]["answered"] is False
    gaps = client.get(f"/api/workspaces/{workspace}/gaps", headers=alice).json()
    q = [g for g in gaps["questions"] if g["source"] == "chat"]
    assert len(q) == 1 and q[0]["times_asked"] == 2


def test_answering_gap_feeds_knowledge_base(client, alice, workspace):
    client.post(f"/api/workspaces/{workspace}/chat/ask", json={"question": "Who is our Kubernetes vendor?"}, headers=alice)
    qid = client.get(f"/api/workspaces/{workspace}/gaps", headers=alice).json()["questions"][0]["id"]
    r = client.patch(
        f"/api/workspaces/{workspace}/questions/{qid}",
        json={"status": "answered", "answer": "Our Kubernetes vendor is Rancher.", "save_as_document": True},
        headers=alice,
    )
    assert r.status_code == 200
    r = client.post(f"/api/workspaces/{workspace}/chat/ask", json={"question": "Who is our Kubernetes vendor?"}, headers=alice)
    assert r.json()["answer"]["answered"] and "Rancher" in r.json()["answer"]["content"]


def test_new_version_supersedes_old(client, alice, workspace):
    v1 = upload(client, workspace, alice, "Pricing Policy v1.txt", b"The Pro plan costs 39 dollars per seat.")
    v2 = upload(client, workspace, alice, "Pricing Policy v2.txt", b"The Pro plan costs 49 dollars per seat.")
    docs = {d["id"]: d for d in client.get(f"/api/workspaces/{workspace}/documents", headers=alice).json()}
    assert docs[v1["id"]]["superseded_by_id"] == v2["id"] and docs[v2["id"]]["version"] == 2
    ans = client.post(f"/api/workspaces/{workspace}/chat/ask", json={"question": "Pro plan cost per seat?"}, headers=alice).json()
    assert "49" in ans["answer"]["content"] and "39" not in ans["answer"]["content"]
    outdated = client.get(f"/api/workspaces/{workspace}/gaps", headers=alice).json()["outdated"]
    assert [o["document"]["id"] for o in outdated] == [v1["id"]]


def test_project_scoping(client, alice, workspace):
    p = client.post(f"/api/workspaces/{workspace}/projects", json={"name": "Mobile"}, headers=alice).json()
    upload(client, workspace, alice, "mobile.txt", b"The mobile app release train ships every second Tuesday.", project_id=p["id"])
    general = client.post(
        f"/api/workspaces/{workspace}/chat/ask",
        json={"question": "When does the mobile release train ship?", "project_id": p["id"]},
        headers=alice,
    ).json()
    assert general["answer"]["answered"]
    other = client.post(f"/api/workspaces/{workspace}/projects", json={"name": "Web"}, headers=alice).json()
    scoped = client.post(
        f"/api/workspaces/{workspace}/chat/ask",
        json={"question": "When does the mobile release train ship?", "project_id": other["id"]},
        headers=alice,
    ).json()
    assert not scoped["answer"]["answered"]


def test_cross_workspace_isolation(client, alice, workspace):
    upload(client, workspace, alice, "pricing.txt", PRICING.encode())
    eve = auth("eve@evil.test")
    other = client.post("/api/workspaces", json={"name": "Evil"}, headers=eve).json()["id"]
    r = client.post(f"/api/workspaces/{other}/chat/ask", json={"question": "How much does the Pro plan cost?"}, headers=eve)
    assert r.json()["answer"]["answered"] is False
