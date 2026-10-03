import os
import time
import uuid
from sqlalchemy import create_engine, String, Text, Integer, Boolean, JSON, ForeignKey, UniqueConstraint, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def uid():
    return str(uuid.uuid4())


def now():
    return int(time.time())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "lab_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    locale: Mapped[str] = mapped_column(String(2), default="es")


class Session(Base):
    __tablename__ = "lab_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("lab_users.id"))
    csrf: Mapped[str] = mapped_column(String(64))
    expires: Mapped[int] = mapped_column(Integer)


class LoginWindow(Base):
    __tablename__ = "lab_login_windows"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    expires: Mapped[int] = mapped_column(Integer)


class Audit(Base):
    __tablename__ = "lab_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    at: Mapped[int] = mapped_column(Integer, default=now)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    resource: Mapped[str] = mapped_column(String(100), default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class Target(Base):
    __tablename__ = "lab_targets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(80))
    adapter: Mapped[str] = mapped_column(String(32), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Run(Base):
    __tablename__ = "lab_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner: Mapped[str] = mapped_column(ForeignKey("lab_users.id"))
    target_id: Mapped[str] = mapped_column(ForeignKey("lab_targets.id"))
    request_key: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16))
    locale: Mapped[str] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    created: Mapped[int] = mapped_column(Integer, default=now)
    started: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ended: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    spec: Mapped[dict] = mapped_column(JSON)
    versions: Mapped[dict] = mapped_column(JSON)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("lab_runs.id"), nullable=True)
    __table_args__ = (UniqueConstraint("owner", "request_key"),)


class Result(Base):
    __tablename__ = "lab_results"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("lab_runs.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    verdict: Mapped[str] = mapped_column(String(24), default="pending_review")
    applicability: Mapped[str] = mapped_column(String(24))
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    attack_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    detected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    blocked: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    benign: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("run_id", "case_id"),)


class Review(Base):
    __tablename__ = "lab_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    result_id: Mapped[str] = mapped_column(ForeignKey("lab_results.id"), index=True)
    actor: Mapped[str] = mapped_column(ForeignKey("lab_users.id"))
    at: Mapped[int] = mapped_column(Integer, default=now)
    verdict: Mapped[str] = mapped_column(String(24))
    criteria: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16))
    impact: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)


class Finding(Base):
    __tablename__ = "lab_findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    target_id: Mapped[str] = mapped_column(ForeignKey("lab_targets.id"))
    case_id: Mapped[str] = mapped_column(String(40))
    mode: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="open")
    assignee: Mapped[str] = mapped_column(String(80), default="")
    created: Mapped[int] = mapped_column(Integer, default=now)
    fixed_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verified_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("target_id", "case_id", "mode"),)


def engine_for(url=None):
    url = url or os.environ["LAB_DATABASE_URL"]
    engine = create_engine(url, pool_pre_ping=True, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def fk(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
    return engine


def sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)


def audit(db, actor, action, resource="", **data):
    db.add(Audit(actor=actor, action=action, resource=resource, data=data))
