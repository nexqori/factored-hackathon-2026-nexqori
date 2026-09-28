import os
import secrets
import time
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, delete, func, or_, text
from sqlalchemy.exc import IntegrityError
from .db import make_engine, make_sessions
from .models import User, Session, Product, Transaction, RequestCase, AuditEvent, Message, now
from .schemas import Login, LocaleInput, RequestInput, ConfirmInput, ChatInput
from .security import db_session, current_session, current_user, csrf, customer, admin, admin_write, digest, verify, hasher, DUMMY_HASH, COOKIE, SESSION_SECONDS, LoginLimiter
from .assistant import answer
from .presentation import present_message

def user_view(user):
    return {"id":user.id,"email":user.email,"name":user.name,"role":user.role,"locale":user.locale}

def request_view(r, name=None):
    return {"id":r.id,"userId":r.user_id,"transactionId":r.transaction_id,"service":r.service,"reason":r.reason,"details":r.details,"status":r.status,"createdAt":r.created_at.isoformat(),"updatedAt":r.updated_at.isoformat(),"customerName":name}

def audit_view(e, name):
    return {"id":e.id,"userId":e.user_id,"requestId":e.request_id,"action":e.action,"actorId":e.actor_id,"actorName":name,"at":e.created_at.isoformat()}

def add_audit(db, user_id, action, actor, request_id=None):
    db.add(AuditEvent(id=str(uuid4()),user_id=user_id,request_id=request_id,action=action,actor_id=actor))

class BodyLimit:
    def __init__(self, app, maximum=16384):
        self.app,self.maximum=app,maximum
    async def __call__(self, scope, receive, send):
        if scope["type"]!="http" or scope["method"] in ("GET","HEAD","OPTIONS"):
            return await self.app(scope,receive,send)
        chunks=[]; total=0
        while True:
            message=await receive()
            if message["type"]=="http.disconnect": return
            chunk=message.get("body",b""); total+=len(chunk)
            if total>self.maximum:
                return await JSONResponse({"error":"payload_too_large"},413)(scope,receive,send)
            chunks.append(chunk)
            if not message.get("more_body"): break
        delivered=False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {"type":"http.request","body":b"".join(chunks),"more_body":False}
            return await receive()
        await self.app(scope,replay,send)

def create_app(engine=None, origins=None, secure_cookies=None, login_limit=10):
    owned_engine=engine is None
    engine=engine or make_engine()
    allowed=origins or os.getenv("APP_ORIGINS","http://localhost:5180,http://127.0.0.1:5180").split(",")
    secure=secure_cookies if secure_cookies is not None else os.getenv("COOKIE_SECURE","true")=="true"
    @asynccontextmanager
    async def lifespan(_):
        yield
        if owned_engine: engine.dispose()
    app=FastAPI(title="Nexqori API",version="0.1.0",docs_url=None,openapi_url="/api/openapi.json",redoc_url=None,lifespan=lifespan)
    app.state.sessions=make_sessions(engine)
    limiter=LoginLimiter(login_limit)
    app.add_middleware(BodyLimit)
    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        if request.method not in ("GET","HEAD","OPTIONS"):
            if request.headers.get("origin") not in allowed:
                return JSONResponse({"error":"origin"},403)
            if request.headers.get("content-type","").split(";")[0].lower()!="application/json":
                return JSONResponse({"error":"json_required"},415)
        response=await call_next(request)
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["X-Frame-Options"]="DENY"
        response.headers["Referrer-Policy"]="same-origin"
        return response
    @app.exception_handler(HTTPException)
    async def http_error(_request, exc):
        return JSONResponse({"error":exc.detail},exc.status_code,headers=exc.headers)
    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, _exc):
        return JSONResponse({"error":"validation"},422)
    @app.get("/api/health")
    def health(db=Depends(db_session)):
        db.execute(text("SELECT 1"))
        return {"status":"ok","app":"nexqori","mode":"local"}
    @app.post("/api/auth/login")
    def login(payload: Login, request: Request, db=Depends(db_session)):
        email=payload.email.strip().lower()
        limiter.consume(request.client.host if request.client else "local",email)
        user=db.scalar(select(User).where(User.email==email))
        if not verify(payload.password,user.password_hash if user else DUMMY_HASH) or not user:
            raise HTTPException(401,"invalid_login")
        limiter.success(email)
        if hasher.check_needs_rehash(user.password_hash): user.password_hash=hasher.hash(payload.password)
        token=secrets.token_hex(32); csrf_token=secrets.token_hex(32)
        db.execute(delete(Session).where(Session.expires_at<=int(time.time())))
        old=request.cookies.get(COOKIE)
        if old: db.execute(delete(Session).where(Session.token_hash==digest(old)))
        db.add(Session(token_hash=digest(token),user_id=user.id,csrf_token=csrf_token,expires_at=int(time.time())+SESSION_SECONDS))
        add_audit(db,user.id,"login",user.id); db.commit()
        response=JSONResponse({"user":user_view(user),"csrfToken":csrf_token})
        response.set_cookie(COOKIE,token,max_age=SESSION_SECONDS,httponly=True,secure=secure,samesite="lax",path="/api")
        return response
    @app.get("/api/session")
    def get_session(auth=Depends(current_session)):
        return {"user":user_view(auth[1]),"csrfToken":auth[0].csrf_token}
    @app.post("/api/auth/logout")
    def logout(user=Depends(csrf),auth=Depends(current_session),db=Depends(db_session)):
        db.delete(auth[0]); add_audit(db,user.id,"logout",user.id); db.commit()
        response=JSONResponse({"ok":True})
        response.delete_cookie(COOKIE,path="/api",httponly=True,secure=secure,samesite="lax")
        return response
    @app.patch("/api/profile/locale")
    def set_locale(payload: LocaleInput,user=Depends(csrf),db=Depends(db_session)):
        user.locale=payload.locale; db.commit()
        return {"user":user_view(user)}
    @app.get("/api/bootstrap")
    def bootstrap(user=Depends(current_user),db=Depends(db_session)):
        products=db.scalars(select(Product).where(Product.user_id==user.id).order_by(Product.id)).all()
        txs=db.scalars(select(Transaction).where(Transaction.user_id==user.id).order_by(Transaction.occurred_at.desc())).all()
        cases=db.scalars(select(RequestCase).where(RequestCase.user_id==user.id).order_by(RequestCase.created_at.desc())).all()
        events=db.execute(select(AuditEvent,User.name).join(User,User.id==AuditEvent.actor_id).where(AuditEvent.user_id==user.id).order_by(AuditEvent.created_at.desc()).limit(250)).all()
        messages=db.scalars(select(Message).where(Message.user_id==user.id).order_by(Message.created_at.desc(),Message.id.desc()).limit(100)).all()
        return {
            "products":[{"id":p.id,"type":p.type,"last4":p.last4,"balanceMinor":p.balance_minor,"currency":p.currency} for p in products],
            "transactions":[{"id":t.id,"productId":t.product_id,"merchant":t.merchant,"category":t.category,"amountMinor":t.amount_minor,"currency":t.currency,"date":t.occurred_at.isoformat(),"status":t.status} for t in txs],
            "requests":[request_view(r) for r in cases],
            "audit":[audit_view(e,name) for e,name in events],
            "messages":[{"id":m.id,"role":m.role,"text":present_message(m.content,m.role),"locale":m.locale,"at":m.created_at.isoformat()} for m in reversed(messages)]
        }
    @app.post("/api/requests")
    def create_request(payload: RequestInput,user=Depends(customer),db=Depends(db_session)):
        details=payload.details.strip()
        if len(details)<10: raise HTTPException(422,"details")
        if payload.transactionId:
            tx=db.scalar(select(Transaction).where(Transaction.id==payload.transactionId,Transaction.user_id==user.id))
            if not tx: raise HTTPException(404,"not_found")
        condition=RequestCase.request_key==payload.requestKey
        if payload.transactionId: condition=or_(condition,RequestCase.transaction_id==payload.transactionId)
        existing=db.scalar(select(RequestCase).where(RequestCase.user_id==user.id,condition))
        if existing: return {"id":existing.id,"duplicate":True}
        case=RequestCase(id="NQ-"+uuid4().hex[:10].upper(),user_id=user.id,transaction_id=payload.transactionId or None,request_key=payload.requestKey,service=payload.service,reason=payload.reason,details=details)
        db.add(case)
        try:
            db.flush()
            add_audit(db,user.id,"created",user.id,case.id); db.commit()
        except IntegrityError:
            db.rollback()
            existing=db.scalar(select(RequestCase).where(RequestCase.user_id==user.id,condition))
            if existing: return {"id":existing.id,"duplicate":True}
            raise HTTPException(409,"conflict")
        return JSONResponse({"id":case.id,"duplicate":False},201)
    @app.post("/api/requests/{request_id}/handoff")
    def handoff(request_id: str,payload: ConfirmInput,user=Depends(customer),db=Depends(db_session)):
        case=db.scalar(select(RequestCase).where(RequestCase.id==request_id,RequestCase.user_id==user.id).with_for_update())
        if not case: raise HTTPException(404,"not_found")
        if case.status!="handed_off":
            case.status="handed_off";case.updated_at=now()
            add_audit(db,user.id,"handed_off",user.id,case.id);db.commit()
        return {"ok":True}
    @app.post("/api/assistant")
    def chat(payload: ChatInput,user=Depends(customer),db=Depends(db_session)):
        message=payload.message.strip()
        if not message: raise HTTPException(422,"invalid_message")
        balance=db.scalar(select(func.coalesce(func.sum(Product.balance_minor),0)).where(Product.user_id==user.id,Product.type.in_(["account","savings"]),Product.currency=="MXN"))
        result=answer(message,payload.locale,balance,payload.currentPage)
        if result["navigation"]: add_audit(db,user.id,"navigate_"+result["navigation"]["destination"],user.id)
        db.add(Message(id=str(uuid4()),user_id=user.id,role="user",content=message,locale=payload.locale))
        db.flush()
        db.add(Message(id=str(uuid4()),user_id=user.id,role="assistant",content=result["text"],locale=payload.locale))
        db.commit()
        return result
    @app.get("/api/admin/overview")
    def admin_overview(_user=Depends(admin),db=Depends(db_session)):
        cases=db.execute(select(RequestCase,User.name).join(User,User.id==RequestCase.user_id).order_by(RequestCase.created_at.desc())).all()
        events=db.execute(select(AuditEvent,User.name).join(User,User.id==AuditEvent.actor_id).order_by(AuditEvent.created_at.desc()).limit(250)).all()
        return {"users":[user_view(u) for u in db.scalars(select(User).order_by(User.name)).all()],"requests":[request_view(r,name) for r,name in cases],"audit":[audit_view(e,name) for e,name in events]}
    @app.post("/api/admin/requests/{request_id}/review")
    def review(request_id: str,payload: ConfirmInput,user=Depends(admin_write),db=Depends(db_session)):
        case=db.scalar(select(RequestCase).where(RequestCase.id==request_id).with_for_update())
        if not case: raise HTTPException(404,"not_found")
        if case.status=="received":
            case.status="in_review";case.updated_at=now()
            add_audit(db,case.user_id,"reviewed",user.id,case.id);db.commit()
        elif case.status!="in_review": raise HTTPException(409,"invalid_transition")
        return {"ok":True}
    return app
