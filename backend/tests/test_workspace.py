from conftest import auth


def test_health(client):
    r = client.get("/api/health")
    assert r.json()["llm"] == "local"


def test_requires_auth(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_create_workspace_makes_owner_and_default_project(client, alice, workspace):
    me = client.get("/api/me", headers=alice).json()
    assert me["workspaces"][0]["role"] == "owner"
    projects = client.get(f"/api/workspaces/{workspace}/projects", headers=alice).json()
    assert [p["name"] for p in projects] == ["General"]


def test_outsiders_cannot_see_workspace(client, workspace, bob):
    assert client.get(f"/api/workspaces/{workspace}", headers=bob).status_code == 404
    assert client.get(f"/api/workspaces/{workspace}/documents", headers=bob).status_code == 404


def test_invite_pending_user_is_claimed_on_first_login(client, alice, workspace):
    r = client.post(f"/api/workspaces/{workspace}/invites", json={"email": "carol@acme.test", "role": "viewer"}, headers=alice)
    assert r.json()["status"] == "invited"
    carol = auth("carol@acme.test")
    me = client.get("/api/me", headers=carol).json()
    assert me["workspaces"][0]["id"] == workspace and me["workspaces"][0]["role"] == "viewer"


def test_roles_are_enforced(client, alice, bob, workspace):
    client.get("/api/me", headers=bob)  # bob signs up
    r = client.post(f"/api/workspaces/{workspace}/invites", json={"email": "bob@acme.test", "role": "viewer"}, headers=alice)
    assert r.json()["status"] == "added"
    # viewers can read and ask, but not write
    assert client.get(f"/api/workspaces/{workspace}/decisions", headers=bob).status_code == 200
    assert client.post(f"/api/workspaces/{workspace}/decisions", json={"title": "Ship it"}, headers=bob).status_code == 403
    assert client.post(f"/api/workspaces/{workspace}/projects", json={"name": "X"}, headers=bob).status_code == 403
    # owner promotes bob to member
    bob_id = client.get("/api/me", headers=bob).json()["user"]["id"]
    assert client.patch(f"/api/workspaces/{workspace}/members/{bob_id}", json={"role": "member"}, headers=alice).status_code == 200
    assert client.post(f"/api/workspaces/{workspace}/decisions", json={"title": "Ship it"}, headers=bob).status_code == 201
    # a member can't escalate themselves
    assert client.patch(f"/api/workspaces/{workspace}/members/{bob_id}", json={"role": "owner"}, headers=bob).status_code == 403


def test_last_owner_cannot_leave(client, alice, workspace):
    alice_id = client.get("/api/me", headers=alice).json()["user"]["id"]
    assert client.delete(f"/api/workspaces/{workspace}/members/{alice_id}", headers=alice).status_code == 400
