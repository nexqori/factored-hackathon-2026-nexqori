from uuid import uuid4
import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from backend.db import make_engine, make_sessions
from backend.models import Base, Session, User, AuditEvent, RequestCase, Transaction
from backend.seed import seed
from backend.main import create_app
from backend.security import digest

ORIGIN = "http://testserver"
PASSWORDS = ["Test-only-customer-2026!", "Test-only-admin-2026!", "Test-only-second-2026!"]

@pytest.fixture
def setup(tmp_path):
    engine=make_engine("sqlite:///" + str(tmp_path/"test.sqlite"))
    Base.metadata.create_all(engine)
    with make_sessions(engine)() as db:
        seed(db,PASSWORDS)
    app=create_app(engine,[ORIGIN],False)
    yield app,engine
    engine.dispose()

def login(app,who="andrea",language=None):
    client=TestClient(app)
    email={"andrea":"andrea@nexqori.local","nora":"admin@nexqori.local","mateo":"mateo@nexqori.local"}[who]
    index={"andrea":0,"nora":1,"mateo":2}[who]
    response=client.post("/api/auth/login",json={"email":email,"password":PASSWORDS[index]},headers={"Origin":ORIGIN})
    assert response.status_code==200,response.text
    client.headers.update({"Origin":ORIGIN,"X-CSRF-Token":response.json()["csrfToken"]})
    return client,response

def payload(**kwargs):
    return {"transactionId":"TX-1002","requestKey":str(uuid4()),"service":"cards","reason":"unknown","details":"I do not recognize this transaction.","confirmed":True,**kwargs}

def test_anonymous_and_origin_boundaries(setup):
    app,_=setup
    client=TestClient(app)
    assert client.get("/api/bootstrap").status_code==401
    assert client.get("/api/admin/overview").status_code==401
    assert client.post("/api/auth/login",json={"email":"andrea@nexqori.local","password":PASSWORDS[0]}).status_code==403
    assert client.post("/api/auth/login",json={},headers={"Origin":"https://unexpected.invalid"}).status_code==403
    assert client.post("/api/auth/login",content="{}",headers={"Origin":ORIGIN,"Content-Type":"text/plain"}).status_code==415

def test_invalid_login_does_not_disclose_account(setup):
    app,_=setup
    client=TestClient(app)
    for email in ["andrea@nexqori.local","missing@nexqori.local"]:
        response=client.post("/api/auth/login",json={"email":email,"password":"wrong-password"},headers={"Origin":ORIGIN})
        assert response.status_code==401
        assert response.json()=={"error":"invalid_login"}

def test_sessions_cookie_hash_expiry_and_logout(setup):
    app,engine=setup
    client,response=login(app)
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    token=client.cookies["nexqori_session"]
    with make_sessions(engine)() as db:
        record=db.get(Session,digest(token))
        assert record and record.token_hash!=token
        assert record.expires_at>time.time()
    assert "password_hash" not in client.get("/api/session").text
    assert client.post("/api/auth/logout",json={}).status_code==200
    assert client.get("/api/bootstrap").status_code==401
    with make_sessions(engine)() as db:
        assert db.get(Session,digest(token)) is None

def test_expired_session_rejected(setup):
    app,engine=setup
    client,_=login(app)
    with make_sessions(engine)() as db:
        record=db.get(Session,digest(client.cookies["nexqori_session"]))
        record.expires_at=0;db.commit()
    assert client.get("/api/bootstrap").status_code==401

def test_csrf_and_role_assignment_rejected(setup):
    app,_=setup
    client,_=login(app)
    assert client.post("/api/requests",json=payload(),headers={"X-CSRF-Token":"bad"}).status_code==403
    assert client.patch("/api/profile/locale",json={"locale":"en","role":"admin"}).status_code==422
    assert client.get("/api/admin/overview").status_code==403
    assert client.post("/api/admin/requests/NQ-1021/review",json={"confirmed":True}).status_code==403

def test_customer_isolation_and_database_owner_constraint(setup):
    app,engine=setup
    client,_=login(app,"mateo")
    result=client.get("/api/bootstrap").json()
    assert {p["id"] for p in result["products"]}=={"account-02"}
    assert {p["id"] for p in result["transactions"]}=={"TX-2001"}
    assert result["requests"]==[]
    assert client.post("/api/requests",json=payload()).status_code==404
    assert client.post("/api/requests/NQ-1021/handoff",json={"confirmed":True}).status_code==404
    with make_sessions(engine)() as db:
        tx=db.get(Transaction,"TX-2001")
        tx.product_id="account-01"
        with pytest.raises(IntegrityError): db.commit()

def test_request_confirmation_and_idempotency(setup):
    app,engine=setup
    client,_=login(app)
    assert client.post("/api/requests",json=payload(confirmed=False)).status_code==422
    assert client.post("/api/requests",json=payload(details="          ")).status_code==422
    request=payload()
    first=client.post("/api/requests",json=request)
    assert first.status_code==201
    second=client.post("/api/requests",json=request)
    third=client.post("/api/requests",json=payload())
    assert second.json()["id"]==third.json()["id"]==first.json()["id"]
    assert second.json()["duplicate"] and third.json()["duplicate"]
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.request_id==first.json()["id"]))==1

def test_general_request_retry_is_idempotent(setup):
    app,_=setup
    client,_=login(app)
    request=payload(transactionId=None,service="loans")
    first=client.post("/api/requests",json=request).json()
    second=client.post("/api/requests",json=request).json()
    assert first["id"]==second["id"]

def test_admin_review_then_customer_handoff(setup):
    app,_=setup
    client,_=login(app)
    case=client.post("/api/requests",json=payload()).json()["id"]
    operator,_=login(app,"nora")
    overview=operator.get("/api/admin/overview")
    assert overview.status_code==200
    assert len(overview.json()["users"])==3
    assert "password_hash" not in overview.text
    assert operator.post("/api/admin/requests/"+case+"/review",json={"confirmed":True}).status_code==200
    assert operator.post("/api/requests",json=payload()).status_code==403
    assert client.post("/api/requests/"+case+"/handoff",json={"confirmed":True}).status_code==200
    assert client.post("/api/requests/"+case+"/handoff",json={"confirmed":True}).status_code==200
    assert operator.post("/api/admin/requests/"+case+"/review",json={"confirmed":True}).status_code==409
    result=client.get("/api/bootstrap").json()
    assert next(r for r in result["requests"] if r["id"]==case)["status"]=="handed_off"
    assert len([e for e in result["audit"] if e["requestId"]==case and e["action"]=="handed_off"])==1

@pytest.mark.parametrize("locale,message,marker",[("es","Mi saldo","Tu saldo"),("en","My balance","Your available"),("pt","Meu saldo","Seu saldo")])
def test_language_saved_and_assistant_scoped(setup,locale,message,marker):
    app,_=setup
    client,_=login(app,"mateo")
    assert client.patch("/api/profile/locale",json={"locale":locale}).status_code==200
    assert client.get("/api/session").json()["user"]["locale"]==locale
    result=client.post("/api/assistant",json={"message":message,"locale":locale})
    assert result.status_code==200
    assert marker in result.json()["text"]
    assert result.json()["destination"]=="products"
    assert "24,850" not in result.json()["text"]
    assert client.patch("/api/profile/locale",json={"locale":"fr"}).status_code==422

def test_ambiguous_chat_never_executes_banking_action(setup):
    app,_=setup
    client,_=login(app)
    before=client.get("/api/bootstrap").json()
    response=client.post("/api/assistant",json={"message":"xyz123","locale":"en"}).json()
    assert response["intent"]=="unknown" and response["destination"] is None
    after=client.get("/api/bootstrap").json()
    assert after["requests"]==before["requests"]
    assert after["products"]==before["products"]
    assert len(after["messages"])==2

def test_payload_limit(setup):
    app,_=setup
    client,_=login(app)
    assert client.post("/api/assistant",json={"message":"x"*18000,"locale":"es"}).status_code==413

def test_navigation_is_audited_and_cannot_create_requests_or_move_money(setup):
    app,_=setup
    client,_=login(app)
    before=client.get('/api/bootstrap').json()
    result=client.post('/api/assistant',json={'message':'Transfer money','locale':'en','currentPage':'home'})
    assert result.status_code==200
    assert result.json()['navigation']['route']=='/services/transfers'
    after=client.get('/api/bootstrap').json()
    assert after['products']==before['products'] and after['transactions']==before['transactions'] and after['requests']==before['requests']
    assert any(e['action']=='navigate_transfers' for e in after['audit'])
    assert client.post('/api/assistant',json={'message':'open','locale':'en','currentPage':'admin'}).status_code==422
    assert client.post('/api/assistant',json={'message':'open admin','locale':'en'}).json()['navigation'] is None
    operator,_=login(app,'nora')
    assert operator.post('/api/assistant',json={'message':'open cards','locale':'en'}).status_code==403

def test_login_rate_limit(setup):
    _,engine=setup
    app=create_app(engine,[ORIGIN],False,login_limit=2)
    client=TestClient(app)
    args={"json":{"email":"andrea@nexqori.local","password":"wrong"},"headers":{"Origin":ORIGIN}}
    assert client.post("/api/auth/login",**args).status_code==401
    assert client.post("/api/auth/login",**args).status_code==401
    response=client.post("/api/auth/login",**args)
    assert response.status_code==429 and response.headers["Retry-After"]=="900"
