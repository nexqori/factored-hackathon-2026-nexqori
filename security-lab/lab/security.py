import hashlib
import os
import re
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, delete
from .db import User, Session, LoginWindow, audit, now

HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY = HASHER.hash(secrets.token_hex(32))
COOKIE = "nexqori_lab_session"
ORIGINS = {"http://localhost:5190", "http://127.0.0.1:5190"}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def verify(value, encoded):
    try:
        return HASHER.verify(encoded, value)
    except (VerificationError, InvalidHashError):
        return False


def redact(value):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if re.search(r"password|token|secret|authorization|cookie|api.?key", k, re.I) else redact(v) for k,v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(password|token|secret|authorization|cookie|api[_-]?key)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", value)
        value = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", value)
        value = re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", value)
        value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", value)
        for name, secret in os.environ.items():
            if re.search(r"PASSWORD|SECRET|API_KEY|TOKEN", name) and len(secret) >= 8:
                value = value.replace(secret, "[REDACTED]")
    return value


def db_session(request: Request):
    with request.app.state.sessions() as db:
        yield db


def authenticated(request: Request, db=Depends(db_session)):
    token = request.cookies.get(COOKIE, "")
    session = db.get(Session, digest(token)) if len(token) == 64 else None
    user = db.get(User, session.user_id) if session else None
    if not session or session.expires <= now() or not user or not user.active:
        raise HTTPException(401, "unauthorized")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf):
            audit(db, user.id, "csrf_denied"); db.commit()
            raise HTTPException(403, "csrf")
    return user, session


def reader(auth=Depends(authenticated)):
    return auth[0]


def operator(user=Depends(reader), db=Depends(db_session)):
    if user.role not in ("admin", "operator"):
        audit(db, user.id, "permission_denied"); db.commit()
        raise HTTPException(403, "forbidden")
    return user


def admin(user=Depends(reader), db=Depends(db_session)):
    if user.role != "admin":
        audit(db, user.id, "permission_denied"); db.commit()
        raise HTTPException(403, "forbidden")
    return user


def rate_limit(db, ip, username):
    # Persistent across API restarts. Single API worker; rows serialized on PostgreSQL.
    db.execute(delete(LoginWindow).where(LoginWindow.expires <= now()))
    for key, limit in [("ip:"+digest(ip), 40), ("user:"+digest(username), 8)]:
        row = db.scalar(select(LoginWindow).where(LoginWindow.key == key).with_for_update())
        if row and row.count >= limit:
            audit(db, "anonymous", "login_limited"); db.commit()
            raise HTTPException(429, "rate_limited", headers={"Retry-After": "900"})
        if row:
            row.count += 1
        else:
            db.add(LoginWindow(key=key, count=1, expires=now()+900))
    db.commit()
