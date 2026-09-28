from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, BigInteger, DateTime, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def now():
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16))
    locale: Mapped[str] = mapped_column(String(2), default="es")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("role IN ('customer','admin')"), CheckConstraint("locale IN ('es','en','pt')"))

class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Product(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    last4: Mapped[str] = mapped_column(String(4))
    balance_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="MXN")
    __table_args__ = (UniqueConstraint("id","user_id"), CheckConstraint("type IN ('account','savings','card')"), CheckConstraint("currency = 'MXN'"))

class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[str] = mapped_column(String(64))
    merchant: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(32))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="MXN")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))
    __table_args__ = (UniqueConstraint("id","user_id"), ForeignKeyConstraint(["product_id","user_id"], ["products.id","products.user_id"]), CheckConstraint("status IN ('completed','pending','declined')"), CheckConstraint("currency = 'MXN'"))

class RequestCase(Base):
    __tablename__ = "requests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_key: Mapped[str] = mapped_column(String(64))
    service: Mapped[str] = mapped_column(String(32), default="general")
    reason: Mapped[str] = mapped_column(String(16))
    details: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(["transaction_id","user_id"], ["transactions.id","transactions.user_id"]),
        UniqueConstraint("user_id","transaction_id"), UniqueConstraint("user_id","request_key"),
        CheckConstraint("status IN ('received','in_review','handed_off')"),
        CheckConstraint("reason IN ('unknown','amount','payment','other')"),
        CheckConstraint("length(details) BETWEEN 10 AND 1000")
    )

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    request_id: Mapped[str | None] = mapped_column(ForeignKey("requests.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("role IN ('user','assistant')"), CheckConstraint("locale IN ('es','en','pt')"))
