import csv
import html
import io
import json
import os
import secrets
import threading
import time
import uuid
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, delete, func, text
from sqlalchemy.exc import IntegrityError
from .db import User, Session, Target, Run, Result, Review, Finding, Audit, engine_for, sessions, audit, now
from .security import HASHER, DUMMY, COOKIE, ORIGINS, verify, digest, redact, rate_limit, db_session, authenticated, reader, operator, admin
from .catalog import CATALOG, BY_ID, CATALOG_HASH, VERSION
from .metrics import summarize, fraction
from .findings import record_finding
from .report import render as render_report

Role=Literal["admin","operator","reader"]
Locale=Literal["es","en","pt"]


class Strict(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)


class Login(Strict):
    username: str=Field(min_length=3,max_length=80,pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str=Field(min_length=1,max_length=256)


class NewUser(Login):
    password: str=Field(min_length=14,max_length=256)
    role: Role


class UserUpdate(Strict):
    role: Role
    active: bool


class LocaleInput(Strict):
    locale: Locale


class TargetInput(Strict):
    name: str=Field(min_length=3,max_length=80)
    adapter: Literal["nexqori-local","demo"]
    enabled: bool=True


class RunInput(Strict):
    target_id: str=Field(max_length=36)
    cases: list[str]=Field(min_length=1,max_length=100)
    locale: Locale="es"
    case_seconds: int=Field(default=20,ge=2,le=30)
    run_seconds: int=Field(default=300,ge=10,le=600)
    requests_per_case: int=Field(default=30,ge=15,le=30)
    parent_id: str | None=Field(default=None,max_length=36)


class ConfirmRun(RunInput):
    confirmed: Literal[True]
    request_key: str=Field(min_length=16,max_length=64,pattern=r"^[A-Za-z0-9-]+$")
    catalog_hash: str=Field(min_length=64,max_length=64)


class ReviewInput(Strict):
    verdict: Literal["passed","failed","inconclusive"]
    criteria: str=Field(min_length=10,max_length=2000)
    evidence: str=Field(min_length=10,max_length=16000)
    severity: Literal["low","medium","high","critical"]="medium"
    impact: str=Field(min_length=10,max_length=2000)
    recommendation: str=Field(min_length=10,max_length=2000)

    @field_validator("evidence")
    @classmethod
    def evidence_bytes(cls,value):
        if len(value.encode("utf-8"))>16000 or "\x00" in value:
            raise ValueError("Evidence must be UTF-8 text up to 16000 bytes")
        return value


class FindingInput(Strict):
    status: Literal["open","fixed"]
    assignee: str=Field(max_length=80)
    note: str=Field(min_length=10,max_length=2000)


class BodyLimit:
    def __init__(self,app): self.app=app
    async def __call__(self,scope,receive,send):
        if scope["type"]!="http" or scope["method"] in ("GET","HEAD","OPTIONS"):
            return await self.app(scope,receive,send)
        body=b""
        while True:
            message=await receive()
            if message["type"]=="http.disconnect": return
            body+=message.get("body",b"")
            if len(body)>32768: return await JSONResponse({"error":"payload_too_large"},413)(scope,receive,send)
            if not message.get("more_body"): break
        delivered=False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {"type":"http.request","body":body,"more_body":False}
            return await receive()
        await self.app(scope,replay,send)


def view(obj):
    data={c.name:getattr(obj,c.name) for c in obj.__table__.columns}
    if isinstance(obj,Run):
        data["spec"]={k:v for k,v in obj.spec.items() if k!="_catalog"}
    return data


def user_view(user):
    return {k:getattr(user,k) for k in ("id","username","role","active","locale")}


def require(db,model,id):
    obj=db.get(model,id)
    if not obj: raise HTTPException(404,"not_found")
    return obj


def effective_results(db,run_id):
    output=[]
    for r in db.scalars(select(Result).where(Result.run_id==run_id).order_by(Result.case_id)):
        item=view(r)
        item["original_verdict"]=r.verdict
        reviews=list(db.scalars(select(Review).where(Review.result_id==r.id).order_by(Review.at,Review.id)))
        item["reviews"]=[view(v) for v in reviews]
        if reviews:
            latest=reviews[-1]
            item["verdict"]=latest.verdict
            if r.applicability=="manual":
                item["evidence"]={**item["evidence"],"executed":True,"manual":True}
            # Manual verdicts without structured attack telemetry never become ASR samples.
            item["attack_success"]=None
        output.append(item)
    return output


def run_detail(db,run):
    results=effective_results(db,run.id)
    return {**view(run),"results":results,"metrics":summarize(results,run.spec.get("_catalog"))}


def versions():
    path=os.path.join(os.path.dirname(__file__),"build.json")
    build=json.load(open(path,encoding="utf-8")) if os.path.exists(path) else {"code":"development-unverified","target":"development-unverified"}
    return {**build,"catalog":CATALOG_HASH,"suite":VERSION,"fixtures":build.get("fixtures","development-unverified"),"evaluator":"http-contract-v1","model":None,"target_mode":"rules"}


def validate_spec(db,payload):
    target=require(db,Target,payload.target_id)
    if not target.enabled: raise HTTPException(409,"target_disabled")
    if target.adapter not in ("nexqori-local","demo"): raise HTTPException(403,"target_denied")
    if len(payload.cases)!=len(set(payload.cases)) or any(c not in BY_ID for c in payload.cases):
        raise HTTPException(422,"invalid_cases")
    if payload.parent_id:
        parent=require(db,Run,payload.parent_id)
        if parent.status in ("pending","running") or parent.target_id!=target.id or parent.locale!=payload.locale:
            raise HTTPException(409,"incompatible_retest")
        if not set(payload.cases).issubset(parent.spec["cases"]): raise HTTPException(409,"incompatible_retest")
    return target


def create_app(engine=None):
    app=FastAPI(title="Nexqori Security Lab",docs_url=None,redoc_url=None,openapi_url=None)
    app.state.sessions=sessions(engine or engine_for())
    app.add_middleware(BodyLimit)
    login_lock=threading.Lock()
    secure=os.getenv("LAB_COOKIE_SECURE","false")=="true"
    allowed=set(os.getenv("LAB_ORIGINS",",".join(ORIGINS)).split(","))

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        if request.method not in ("GET","HEAD","OPTIONS"):
            if request.headers.get("origin") not in allowed:
                return JSONResponse({"error":"origin"},403)
            if request.headers.get("content-type","").split(";")[0]!="application/json":
                return JSONResponse({"error":"json_required"},415)
        response=await call_next(request)
        response.headers.update({"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","X-Frame-Options":"DENY","Content-Security-Policy":"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'","Referrer-Policy":"no-referrer"})
        return response

    @app.exception_handler(HTTPException)
    async def http_error(_,exc): return JSONResponse({"error":exc.detail},exc.status_code,headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid(_,exc): return JSONResponse({"error":"validation"},422)

    @app.exception_handler(Exception)
    async def internal(_,exc): return JSONResponse({"error":"internal_error"},500)

    @app.get("/api/health")
    def health(db=Depends(db_session)):
        db.execute(text("SELECT 1")); return {"status":"ok","app":"nexqori-security-lab"}

    @app.post("/api/login")
    def login(payload: Login,request: Request,db=Depends(db_session)):
        username=payload.username.lower()
        with login_lock:
            rate_limit(db,request.client.host if request.client else "local",username)
        user=db.scalar(select(User).where(User.username==username))
        valid=verify(payload.password,user.password_hash if user else DUMMY)
        if not valid or not user or not user.active:
            audit(db,"anonymous","login_failed");db.commit();raise HTTPException(401,"invalid_login")
        token=secrets.token_hex(32);csrf=secrets.token_hex(32)
        db.execute(delete(Session).where(Session.expires<=now()))
        old=request.cookies.get(COOKIE)
        if old: db.execute(delete(Session).where(Session.token_hash==digest(old)))
        db.add(Session(token_hash=digest(token),user_id=user.id,csrf=csrf,expires=now()+28800))
        audit(db,user.id,"login");db.commit()
        response=JSONResponse({"user":user_view(user),"csrf":csrf})
        response.set_cookie(COOKIE,token,max_age=28800,httponly=True,secure=secure,samesite="strict",path="/api")
        return response

    @app.get("/api/session")
    def session(auth=Depends(authenticated)): return {"user":user_view(auth[0]),"csrf":auth[1].csrf}

    @app.post("/api/logout")
    def logout(auth=Depends(authenticated),db=Depends(db_session)):
        db.delete(auth[1]);audit(db,auth[0].id,"logout");db.commit()
        response=JSONResponse({"ok":True});response.delete_cookie(COOKIE,path="/api",httponly=True,secure=secure,samesite="strict");return response

    @app.patch("/api/locale")
    def locale(payload: LocaleInput,user=Depends(reader),db=Depends(db_session)):
        user.locale=payload.locale;db.commit();return user_view(user)

    @app.get("/api/catalog")
    def catalog(_=Depends(reader)): return {"version":VERSION,"hash":CATALOG_HASH,"cases":CATALOG}

    @app.get("/api/users")
    def users(_=Depends(admin),db=Depends(db_session)): return [user_view(u) for u in db.scalars(select(User).order_by(User.username))]

    @app.post("/api/users")
    def new_user(payload: NewUser,user=Depends(admin),db=Depends(db_session)):
        u=User(username=payload.username.lower(),password_hash=HASHER.hash(payload.password),role=payload.role)
        db.add(u)
        try: db.flush()
        except IntegrityError: db.rollback();raise HTTPException(409,"conflict")
        audit(db,user.id,"user_created",u.id,role=u.role);db.commit();return user_view(u)

    @app.patch("/api/users/{id}")
    def update_user(id: str,payload: UserUpdate,user=Depends(admin),db=Depends(db_session)):
        u=require(db,User,id)
        if u.id==user.id: raise HTTPException(409,"self_change_denied")
        u.role=payload.role;u.active=payload.active
        db.execute(delete(Session).where(Session.user_id==u.id))
        audit(db,user.id,"user_updated",u.id,role=u.role,active=u.active);db.commit();return user_view(u)

    @app.get("/api/targets")
    def targets(_=Depends(reader),db=Depends(db_session)): return [view(t) for t in db.scalars(select(Target).order_by(Target.name))]

    @app.patch("/api/targets/{id}")
    def target_update(id: str,payload: TargetInput,user=Depends(admin),db=Depends(db_session)):
        t=require(db,Target,id)
        if payload.adapter!=t.adapter: raise HTTPException(409,"adapter_immutable")
        t.name=payload.name;t.enabled=payload.enabled
        audit(db,user.id,"target_updated",id,enabled=t.enabled);db.commit();return view(t)

    @app.post("/api/runs/preview")
    def preview(payload: RunInput,_=Depends(operator),db=Depends(db_session)):
        target=validate_spec(db,payload)
        return dict(target=view(target),spec=payload.model_dump(),catalog_hash=CATALOG_HASH,versions=versions(),
            cases=[BY_ID[c] for c in payload.cases],max_requests=len(payload.cases)*payload.requests_per_case,concurrency=1)

    @app.post("/api/runs",status_code=201)
    def create_run(payload: ConfirmRun,user=Depends(operator),db=Depends(db_session)):
        if db.bind.dialect.name=="postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(520002)"))
        target=validate_spec(db,payload)
        if payload.catalog_hash!=CATALOG_HASH: raise HTTPException(409,"catalog_changed")
        spec=payload.model_dump(exclude={"confirmed","request_key","catalog_hash"})
        existing=db.scalar(select(Run).where(Run.owner==user.id,Run.request_key==payload.request_key))
        if existing:
            if {k:v for k,v in existing.spec.items() if k!="_catalog"}!=spec: raise HTTPException(409,"idempotency_conflict")
            return view(existing)
        if db.scalar(select(func.count()).select_from(Run).where(Run.status.in_(["pending","running"])))>=10:
            raise HTTPException(429,"queue_full")
        run=Run(owner=user.id,target_id=target.id,request_key=payload.request_key,mode="demo" if target.adapter=="demo" else "real",locale=payload.locale,spec={**spec,"_catalog":CATALOG},versions=versions(),parent_id=payload.parent_id)
        db.add(run);db.flush()
        for cid in payload.cases: db.add(Result(run_id=run.id,case_id=cid,applicability=BY_ID[cid]["mode"]))
        audit(db,user.id,"run_confirmed",run.id,spec=spec);db.commit();return view(run)

    @app.get("/api/runs")
    def runs(_=Depends(reader),db=Depends(db_session)):
        return [view(r) for r in db.scalars(select(Run).order_by(Run.created.desc(),Run.id).limit(200))]

    @app.get("/api/runs/{id}")
    def get_run(id: str,_=Depends(reader),db=Depends(db_session)): return run_detail(db,require(db,Run,id))

    @app.post("/api/runs/{id}/cancel")
    def cancel(id: str,user=Depends(operator),db=Depends(db_session)):
        run=require(db,Run,id)
        if run.status in ("pending","running"):
            run.cancelled=True
            if run.status=="pending":
                run.status="cancelled";run.ended=now()
                for r in db.scalars(select(Result).where(Result.run_id==id)):
                    r.status="cancelled";r.verdict="inconclusive";r.evidence={"executed":False,"error":"cancelled"}
            audit(db,user.id,"run_cancel_requested",id);db.commit()
        return view(run)

    @app.post("/api/results/{id}/reviews")
    def review(id: str,payload: ReviewInput,user=Depends(operator),db=Depends(db_session)):
        result=db.scalar(select(Result).where(Result.id==id).with_for_update())
        if not result: raise HTTPException(404,"not_found")
        run=require(db,Run,result.run_id)
        if run.status in ("pending","running") or result.applicability in ("blocked","not_applicable"):
            raise HTTPException(409,"not_reviewable")
        if result.status in ("error","cancelled") and payload.verdict!="inconclusive": raise HTTPException(409,"not_reviewable")
        item=Review(id=str(uuid.UUID(int=time.time_ns())),result_id=id,actor=user.id,**redact(payload.model_dump()));db.add(item);db.flush()
        # Preserve machine result. Only a temporary view is passed to finding lifecycle.
        original=result.verdict;result.verdict=payload.verdict
        record_finding(db,run,result,user.id,redact(payload.model_dump()))
        result.verdict=original
        audit(db,user.id,"review_added",id,review_id=item.id);db.commit();return view(item)

    @app.get("/api/findings")
    def findings(_=Depends(reader),db=Depends(db_session)): return [view(f) for f in db.scalars(select(Finding).order_by(Finding.created.desc()))]

    @app.patch("/api/findings/{id}")
    def finding_update(id: str,payload: FindingInput,user=Depends(operator),db=Depends(db_session)):
        f=require(db,Finding,id);f.status=payload.status;f.assignee=payload.assignee
        f.fixed_at=now() if payload.status=="fixed" else None;f.verified_at=None
        audit(db,user.id,"finding_updated",id,**redact(payload.model_dump()));db.commit();return view(f)

    @app.get("/api/audit")
    def audits(_=Depends(admin),db=Depends(db_session)): return [view(a) for a in db.scalars(select(Audit).order_by(Audit.at.desc(),Audit.id).limit(500))]

    @app.get("/api/compare/{first}/{second}")
    def compare(first: str,second: str,_=Depends(reader),db=Depends(db_session)):
        a,b=require(db,Run,first),require(db,Run,second)
        comparable=(a.target_id==b.target_id and a.mode==b.mode and a.locale==b.locale and sorted(a.spec["cases"])==sorted(b.spec["cases"]) and all(a.versions.get(k)==b.versions.get(k) for k in ("catalog","fixtures","evaluator","model","target_mode")) and all(a.spec[k]==b.spec[k] for k in ("case_seconds","run_seconds","requests_per_case")))
        return dict(comparable=comparable,first=run_detail(db,a),second=run_detail(db,b),reason=None if comparable else "incompatible_runs")

    @app.get("/api/program/{mode}")
    def program(mode: Literal["real","demo"],_=Depends(reader),db=Depends(db_session)):
        rows=list(db.scalars(select(Finding).where(Finding.mode==mode)))
        fixed=[f for f in rows if f.fixed_at is not None]
        return dict(mode=mode,total=len(rows),by_severity={s:sum(f.severity==s for f in rows) for s in ("low","medium","high","critical")},
            by_status={s:sum(f.status==s for f in rows) for s in ("open","fixed","verified")},
            mttr_seconds=sum(f.fixed_at-f.created for f in fixed)/len(fixed) if fixed else None,mttr_n=len(fixed),
            regressions=sum(f.data.get("regressions",0) for f in rows))

    @app.get("/api/runs/{id}/export/{format}")
    def export(id: str,format: Literal["json","csv","html"],user=Depends(reader),db=Depends(db_session)):
        run=require(db,Run,id);data=run_detail(db,run)
        data["catalog"]=[c for c in run.spec.get("_catalog",CATALOG) if c["id"] in run.spec["cases"]]
        data["findings"]=[view(f) for f in db.scalars(select(Finding).where(Finding.target_id==run.target_id,Finding.mode==run.mode)) if any(r["id"] in f.data.get("occurrences",[]) for r in data["results"])]
        data["limitations"]="Local synthetic rules target; no LLM assurance or certification. Null telemetry is not zero risk. Demo is simulated. Manual evidence requires review."
        audit(db,user.id,"report_exported",id,format=format);db.commit()
        data=redact(data)
        if format=="json": body=json.dumps(data,ensure_ascii=False,indent=2);media="application/json"
        elif format=="csv":
            output=io.StringIO();writer=csv.writer(output);writer.writerow(["case","status","verdict","evidence"])
            for r in data["results"]:
                cells=[r["case_id"],r["status"],r["verdict"],json.dumps(r,ensure_ascii=False)]
                writer.writerow(["'"+s if s.lstrip().startswith(("=","+","-","@","\t","\r")) else s for s in cells])
            body=output.getvalue();media="text/csv"
        else:
            body=render_report(data)
            media="text/html"
        return Response(body,media_type=media,headers={"Content-Disposition":f'attachment; filename="security-lab-{id}.{format}"'})

    return app
