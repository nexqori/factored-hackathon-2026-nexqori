from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.main import create_app
from backend.models import Message, Conversation
from backend.db import make_sessions
from backend.tests.test_api import setup, login, ORIGIN, PASSWORDS


def say(client, text="Mi saldo", cid=None, locale="es"):
    return client.post("/api/assistant", json={"message":text,"conversationId":cid,"locale":locale})


def test_new_resume_and_ownership(setup):
    app, engine = setup
    andrea, _ = login(app)
    mateo, _ = login(app, "mateo")
    a = say(andrea).json()
    b = say(andrea, "Ver mis tarjetas").json()
    aid, bid = a["conversation"]["id"], b["conversation"]["id"]
    assert aid != bid
    assert "messages" not in andrea.get("/api/bootstrap").json()
    assert len(andrea.get("/api/conversations").json()["conversations"]) == 2
    assert mateo.get("/api/conversations").json()["conversations"] == []
    assert mateo.get("/api/conversations/"+aid).status_code == 404
    assert say(mateo, cid=aid).status_code == 404
    resumed = say(andrea, "Ver pagos", cid=aid).json()
    assert resumed["conversation"]["id"] == aid
    detail = andrea.get("/api/conversations/"+aid).json()
    assert [m["text"] for m in detail["messages"] if m["role"] == "user"] == ["Mi saldo", "Ver pagos"]
    assert len(andrea.get("/api/conversations/"+bid).json()["messages"]) == 2
    admin, _ = login(app, "nora")
    assert admin.get("/api/conversations").status_code == 403
    assert TestClient(app).get("/api/conversations").status_code == 401
    with make_sessions(engine)() as db:
        db.add(Message(id=str(uuid4()), user_id="mateo", conversation_id=aid, role="user", content="forbidden", locale="es"))
        with pytest.raises(IntegrityError): db.commit()


def test_history_pagination_preserves_order_and_owner_cursor(setup):
    app, engine = setup
    client, _ = login(app)
    first = say(client).json()["conversation"]["id"]
    second = say(client, "Otra conversación").json()
    with make_sessions(engine)() as db:
        for i in range(58):
            db.add(Message(id=str(uuid4()), user_id="andrea", conversation_id=first, role="user", content=f"message {i}", locale="es"))
        for i in range(25):
            db.add(Conversation(id=str(uuid4()), user_id="andrea", title=f"Topic {i}", locale="en"))
        db.commit()
    latest = client.get("/api/conversations/"+first).json()
    previous = client.get("/api/conversations/"+first+"?before="+latest["before"]).json()
    assert len(latest["messages"]) == 50 and len(previous["messages"]) == 10
    assert len({m["id"] for m in previous["messages"] + latest["messages"]}) == 60
    assert previous["before"] is None
    foreign_cursor = second["messages"][0]["id"]
    assert client.get("/api/conversations/"+first+"?before="+foreign_cursor).status_code == 404
    page1 = client.get("/api/conversations").json()
    page2 = client.get("/api/conversations?offset="+str(page1["nextOffset"])).json()
    assert len(page1["conversations"]) == 20 and len(page2["conversations"]) == 7
    assert page2["nextOffset"] is None
    assert not set(c["id"] for c in page1["conversations"]) & set(c["id"] for c in page2["conversations"])


@pytest.mark.parametrize("identifier", ["andrea@nexqori.com", "  ANDREA@nexqori.com ", "00000001", "0000-0001"])
def test_login_with_email_or_identity(setup, identifier):
    app, _ = setup
    result = TestClient(app).post("/api/auth/login", json={"identifier":identifier,"password":PASSWORDS[0]}, headers={"Origin":ORIGIN})
    assert result.status_code == 200
    assert result.json()["user"]["id"] == "andrea"
    assert "identity" not in result.text and "00000001" not in result.text


def test_login_aliases_share_rate_limit(setup):
    _, engine = setup
    client = TestClient(create_app(engine, [ORIGIN], False, login_limit=2))
    for identifier, status in [("andrea@nexqori.com",401), ("00000001",401), ("0000-0001",429)]:
        result = client.post("/api/auth/login", json={"identifier":identifier,"password":"wrong"}, headers={"Origin":ORIGIN})
        assert result.status_code == status


def test_reading_preferences_persist_and_are_isolated(setup):
    app, _ = setup
    client, _ = login(app)
    other, _ = login(app, "mateo")
    for size in ["small", "medium", "large"]:
        assert client.patch("/api/profile/preferences", json={"textSize":size}).status_code == 200
        assert client.get("/api/session").json()["user"]["textSize"] == size
    assert other.get("/api/session").json()["user"]["textSize"] == "medium"
    assert client.patch("/api/profile/preferences", json={"textSize":"huge"}).status_code == 422
    assert client.patch("/api/profile/preferences", json={"textSize":"small"}, headers={"X-CSRF-Token":"bad"}).status_code == 403
