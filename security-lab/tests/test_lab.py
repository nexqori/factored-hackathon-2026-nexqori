import json
import secrets
import time
import threading
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from lab.api import create_app, effective_results
from lab.catalog import CATALOG, CATALOG_HASH
from lab.db import Base, User, Target, Run, Result, Review, Finding, Session, Audit, engine_for, sessions, now
from lab.security import HASHER, COOKIE, digest, redact
from lab.metrics import summarize
from lab.worker import recover, execute_run

ORIGIN="http://localhost:5190"


@pytest.fixture
def setup(tmp_path):
    engine=engine_for("sqlite:///"+str(tmp_path/"lab.sqlite"))
    Base.metadata.create_all(engine)
    factory=sessions(engine)
    password=secrets.token_hex(16)
    with factory() as db:
        for role in ("admin","operator","reader"):
            db.add(User(username=role,password_hash=HASHER.hash(password),role=role))
        db.add_all([Target(id="real",name="Local rules",adapter="nexqori-local"),Target(id="demo",name="Simulation",adapter="demo")]);db.commit()
    app=create_app(engine)
    yield app,factory,password
    engine.dispose()


def login(setup,role="admin"):
    app,_,password=setup
    c=TestClient(app)
    r=c.post("/api/login",json={"username":role,"password":password},headers={"Origin":ORIGIN})
    assert r.status_code==200,r.text
    c.headers.update({"Origin":ORIGIN,"X-CSRF-Token":r.json()["csrf"]})
    return c


def spec(**changes):
    return dict(target_id="demo",cases=["LLM06-05"],locale="es",case_seconds=20,run_seconds=300,requests_per_case=30,parent_id=None,**changes)


def create(c,payload=None):
    p=payload or spec()
    preview=c.post("/api/runs/preview",json=p)
    assert preview.status_code==200,preview.text
    r=c.post("/api/runs",json={**p,"confirmed":True,"catalog_hash":CATALOG_HASH,"request_key":secrets.token_hex(16)})
    assert r.status_code==201,r.text
    return r.json()


def test_anonymous_resources(setup):
    c=TestClient(setup[0])
    for route in ("/catalog","/runs","/findings","/targets","/users","/audit","/runs/no/export/html"):
        assert c.get("/api"+route).status_code==401


def test_origins_csrf_cookies_and_revocation(setup):
    c=login(setup)
    assert c.cookies.get(COOKIE)
    assert c.post("/api/logout",json={},headers={"Origin":"https://evil.invalid"}).status_code==403
    assert c.post("/api/logout",json={},headers={"X-CSRF-Token":"bad"}).status_code==403
    token=c.cookies.get(COOKIE)
    assert c.post("/api/logout",json={}).status_code==200
    c.cookies.set(COOKIE,token)
    assert c.get("/api/session").status_code==401
    c.cookies.clear();c.cookies.set("nexqori_session",token)
    assert c.get("/api/session").status_code==401


def test_login_cookie_flags(setup):
    c=TestClient(setup[0]);r=c.post("/api/login",json={"username":"admin","password":setup[2]},headers={"Origin":ORIGIN})
    cookie=r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie


def test_reader_cannot_execute_or_admin(setup):
    c=login(setup,"reader")
    assert c.post("/api/runs/preview",json=spec()).status_code==403
    assert c.get("/api/users").status_code==403
    assert c.get("/api/audit").status_code==403
    assert c.get("/api/catalog").status_code==200


def test_operator_permissions(setup):
    c=login(setup,"operator")
    assert c.post("/api/runs/preview",json=spec()).status_code==200
    assert c.patch("/api/targets/demo",json={"name":"xxy","adapter":"demo","enabled":False}).status_code==403


def test_disable_revokes_sessions(setup):
    admin=login(setup);op=login(setup,"operator")
    user=next(u for u in admin.get("/api/users").json() if u["role"]=="operator")
    assert admin.patch("/api/users/"+user["id"],json={"role":"reader","active":False}).status_code==200
    assert op.get("/api/session").status_code==401


def test_session_expiry(setup):
    c=login(setup)
    with setup[1]() as db:
        s=db.get(Session,digest(c.cookies.get(COOKIE)));s.expires=now()-1;db.commit()
    assert c.get("/api/session").status_code==401


def test_login_limit_persists_and_generic_error(setup):
    c=TestClient(setup[0]);headers={"Origin":ORIGIN}
    for _ in range(8):
        r=c.post("/api/login",json={"username":"missing","password":"wrong"},headers=headers)
        assert r.status_code==401 and r.json()=={"error":"invalid_login"}
    assert c.post("/api/login",json={"username":"missing","password":"wrong"},headers=headers).status_code==429


def test_target_allowlist_and_no_arbitrary_url(setup):
    c=login(setup)
    assert c.post("/api/runs/preview",json={**spec(),"url":"http://169.254.169.254/"}).status_code==422
    assert c.post("/api/runs/preview",json={**spec(),"target_id":"http://localhost:5180"}).status_code==404
    assert c.patch("/api/targets/demo",json={"name":"Test target","adapter":"nexqori-local","enabled":True}).status_code==409
    assert c.patch("/api/targets/demo",json={"name":"Test target","adapter":"demo","enabled":False}).status_code==200
    assert c.post("/api/runs/preview",json=spec()).status_code==409


def test_confirmation_idempotency_and_limits(setup):
    c=login(setup)
    body={**spec(),"catalog_hash":CATALOG_HASH,"request_key":secrets.token_hex(16)}
    assert c.post("/api/runs",json=body).status_code==422
    body["confirmed"]=True
    a=c.post("/api/runs",json=body);b=c.post("/api/runs",json=body)
    assert a.json()["id"]==b.json()["id"]
    assert c.post("/api/runs",json={**body,"locale":"pt"}).status_code==409
    assert c.post("/api/runs/preview",json={**spec(),"case_seconds":999}).status_code==422
    assert c.post("/api/runs/preview",json={**spec(),"cases":["missing"]}).status_code==422


def test_body_and_error_redaction(setup):
    c=login(setup)
    r=c.post("/api/runs/preview",json={**spec(),"secret":"x"*34000})
    assert r.status_code==413
    r=c.post("/api/runs/preview",json={"password":"private"})
    assert r.status_code==422 and "private" not in r.text
    assert redact({"password":"xyz","evidence":"token=abc sk-secret123"})=={"password":"[REDACTED]","evidence":"token=[REDACTED] [REDACTED]"}


def test_catalog_full_methods_and_locales():
    assert len(CATALOG)==66
    assert len({c["id"] for c in CATALOG})==66
    assert len([c for c in CATALOG if c["id"].startswith("LLM")])==56
    assert {c["category"] for c in CATALOG}=={f"LLM{i:02}:2025" for i in range(1,11)}
    for c in CATALOG:
        for key in ("title","objective","reason","expected","cleanup","fixtures","evidence"):
            assert set(c[key])=={"es","en","pt"}
        assert bool(c["executor"])==(c["mode"]=="automated")


def test_metrics_denominators_and_no_telemetry():
    blank=summarize([])
    assert blank["asr"]["value"] is None
    base=dict(case_id="NQ-auth",evidence={"executed":True},applicability="automated",status="completed",verdict="passed",benign=False,attack_success=False,detected=None,duration_ms=10)
    result=summarize([base,{**base,"case_id":"LLM01-01","status":"error","verdict":"inconclusive","attack_success":None,"evidence":{"executed":False}}])
    assert result["asr"]=={"numerator":0,"denominator":1,"value":0}
    assert result["coverage"]["numerator"]==1
    assert result["detection"]["value"] is None
    assert result["infrastructure_errors"]==1


def test_recovery_never_replays_effects(setup):
    c=login(setup);run=create(c)
    with setup[1]() as db:
        db.get(Run,run["id"]).status="running";db.commit()
    recover(setup[1])
    r=c.get("/api/runs/"+run["id"]).json()
    assert r["status"]=="error" and r["results"][0]["verdict"]=="inconclusive"
    assert r["results"][0]["evidence"]["error"]=="worker_restart_no_replay"


def test_cancel_queued(setup):
    c=login(setup);run=create(c)
    assert c.post("/api/runs/"+run["id"]+"/cancel",json={}).json()["status"]=="cancelled"
    r=c.get("/api/runs/"+run["id"]).json()
    assert all(x["status"]=="cancelled" for x in r["results"])
    assert r["metrics"]["coverage"]["numerator"]==0


def test_manual_evidence_immutable_and_safe_exports(setup):
    c=login(setup);run=create(c,{**spec(),"cases":["LLM03-02"]})
    with setup[1]() as db:
        r=db.get(Run,run["id"]);r.status="completed"
        result=db.scalar(select(Result).where(Result.run_id==r.id));result.status="completed";rid=result.id;db.commit()
    payload=dict(verdict="failed",criteria="Tool may access foreign data",evidence="<script>alert('x')</script> token=private",severity="high",impact="May reveal synthetic private data",recommendation="Enforce ownership in the reader")
    assert c.post("/api/results/"+rid+"/reviews",json=payload).status_code==200
    data=c.get("/api/runs/"+run["id"]).json()
    assert data["results"][0]["verdict"]=="failed"
    with setup[1]() as db: assert db.get(Result,rid).verdict=="pending_review"
    report=c.get("/api/runs/"+run["id"]+"/export/html")
    assert "<script>" not in report.text and "&lt;script&gt;" in report.text
    assert "token=private" not in report.text
    assert c.get("/api/runs/"+run["id"]+"/export/json").json()["results"][0]["reviews"]
    assert c.get("/api/runs/"+run["id"]+"/export/csv").status_code==200


def test_blocked_cannot_be_passed_by_review(setup):
    c=login(setup);run=create(c,{**spec(),"cases":["LLM01-01"]})
    with setup[1]() as db:
        db.get(Run,run["id"]).status="completed";result=db.scalar(select(Result).where(Result.run_id==run["id"]));rid=result.id;db.commit()
    payload=dict(verdict="passed",criteria="Unsupported hypothetical criterion",evidence="No model was tested at all",impact="Unknown security consequences",recommendation="Connect authorized isolated model")
    assert c.post("/api/results/"+rid+"/reviews",json=payload).status_code==409


def test_compare_separates_modes(setup):
    c=login(setup);a=create(c);b=create(c,{**spec(),"target_id":"real"})
    assert c.get(f'/api/compare/{a["id"]}/{b["id"]}').json()["comparable"] is False


def test_demo_worker_persists_findings(setup):
    c=login(setup);run=create(c)
    with setup[1]() as db:
        db.get(Run,run["id"]).status="running";db.commit()
    execute_run(setup[1],run["id"])
    data=c.get("/api/runs/"+run["id"]).json()
    assert data["status"]=="completed"
    assert data["results"][0]["evidence"]["simulated"] is True
    assert data["results"][0]["verdict"]=="failed"
    assert c.get("/api/program/demo").json()["total"]==1
    assert c.get("/api/program/real").json()["total"]==0


def test_worker_handles_manual_blocked_na(setup):
    c=login(setup);run=create(c,{**spec(),"cases":["LLM03-02","LLM01-01","LLM08-01"]})
    execute_run(setup[1],run["id"])
    data=c.get("/api/runs/"+run["id"]).json()
    assert {r["verdict"] for r in data["results"]}=={"pending_review","inconclusive","not_applicable"}
    assert data["metrics"]["coverage"]["numerator"]==0


def slow_executor(queue, *args):
    time.sleep(20)


def test_cancel_active_process(setup,monkeypatch):
    import lab.worker as worker
    monkeypatch.setattr(worker,"child_execute",slow_executor)
    c=login(setup);run=create(c)
    with setup[1]() as db:
        db.get(Run,run["id"]).status="running";db.commit()
    def stop():
        time.sleep(.8)
        with setup[1]() as db:
            db.get(Run,run["id"]).cancelled=True;db.commit()
    thread=threading.Thread(target=stop);thread.start()
    start=time.monotonic();execute_run(setup[1],run["id"]);thread.join()
    assert time.monotonic()-start<5
    data=c.get("/api/runs/"+run["id"]).json()
    assert data["status"]=="cancelled" and data["results"][0]["verdict"]=="inconclusive"


def test_hard_case_deadline(setup,monkeypatch):
    import lab.worker as worker
    monkeypatch.setattr(worker,"child_execute",slow_executor)
    c=login(setup);run=create(c,{**spec(),"case_seconds":2})
    start=time.monotonic();execute_run(setup[1],run["id"])
    assert time.monotonic()-start<5
    data=c.get("/api/runs/"+run["id"]).json()
    assert data["status"]=="error"
    assert data["results"][0]["evidence"]["error"]=="case_timeout"
