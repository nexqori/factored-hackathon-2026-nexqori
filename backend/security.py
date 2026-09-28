import hashlib
import secrets
import threading
import time
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import HTTPException, Request, Depends
from sqlalchemy import select
from .models import Session, User

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))
COOKIE = "nexqori_session"
SESSION_SECONDS = 8 * 60 * 60

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def verify(password, encoded):
    try:
        return hasher.verify(encoded, password)
    except (VerifyMismatchError, VerificationError):
        return False

def db_session(request: Request):
    with request.app.state.sessions() as session:
        yield session

def current_session(request: Request, db=Depends(db_session)):
    token = request.cookies.get(COOKIE, "")
    if len(token) != 64:
        raise HTTPException(401, "unauthorized")
    record = db.get(Session, digest(token))
    if not record or record.expires_at <= int(time.time()):
        raise HTTPException(401, "unauthorized")
    user = db.get(User, record.user_id)
    if not user:
        raise HTTPException(401, "unauthorized")
    return record, user

def current_user(auth=Depends(current_session)):
    return auth[1]

def csrf(request: Request, auth=Depends(current_session)):
    if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), auth[0].csrf_token):
        raise HTTPException(403, "csrf")
    return auth[1]

def customer(user=Depends(csrf)):
    if user.role != "customer":
        raise HTTPException(403, "forbidden")
    return user

def admin(user=Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "forbidden")
    return user

def admin_write(user=Depends(csrf)):
    if user.role != "admin":
        raise HTTPException(403, "forbidden")
    return user

class LoginLimiter:
    # Single API process in the local Compose topology.
    def __init__(self, limit=10):
        self.limit = limit
        self.entries = {}
        self.lock = threading.Lock()

    def consume(self, ip, email):
        now = time.time()
        with self.lock:
            self.entries = {k: v for k, v in self.entries.items() if v[1] > now}
            for key, limit in [("ip:" + ip, self.limit * 5), ("email:" + digest(email), self.limit)]:
                count, until = self.entries.get(key, (0, now + 900))
                if len(self.entries) >= 10000 or count >= limit:
                    raise HTTPException(429, "rate_limited", headers={"Retry-After":"900"})
                self.entries[key] = (count + 1, until)

    def success(self, email):
        with self.lock:
            self.entries.pop("email:" + digest(email), None)
