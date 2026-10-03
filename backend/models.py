from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, BigInteger, Boolean, Date, DateTime, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, JSON, LargeBinary
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import date

def now():
    return datetime.now(timezone.utc)

def iso_utc(value):
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    identity_number: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16))
    locale: Mapped[str] = mapped_column(String(2), default="es")
    text_size: Mapped[str] = mapped_column(String(8), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    profile: Mapped["CustomerProfile | None"] = relationship(lazy="selectin", uselist=False)
    __table_args__ = (CheckConstraint("role IN ('customer','admin')"), CheckConstraint("locale IN ('es','en','pt')"), CheckConstraint("text_size IN ('small','medium','large')"))

class CustomerProfile(Base):
    __tablename__ = "customer_profiles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    birth_date: Mapped[date] = mapped_column(Date)
    banking_experience: Mapped[str] = mapped_column(String(16))
    digital_experience: Mapped[str] = mapped_column(String(16))
    assistance: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        CheckConstraint("banking_experience IN ('new','occasional','frequent')"),
        CheckConstraint("digital_experience IN ('new','learning','confident')"),
        CheckConstraint("assistance IN ('auto','guided','standard')"),
    )

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
    transfer_reference: Mapped[str | None] = mapped_column(String(18), unique=True, nullable=True)
    __table_args__ = (UniqueConstraint("id","user_id"), CheckConstraint("type IN ('account','savings','card')"), CheckConstraint("currency = 'MXN'"))

class CardProfile(Base):
    __tablename__ = "card_profiles"
    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_ref: Mapped[str] = mapped_column(String(64), unique=True)
    expiry_month: Mapped[int] = mapped_column(Integer)
    expiry_year: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    block_request_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    settlement_product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(["product_id", "user_id"], ["products.id", "products.user_id"]),
        ForeignKeyConstraint(["settlement_product_id", "user_id"], ["products.id", "products.user_id"], name="fk_card_settlement_owner"),
        UniqueConstraint("user_id", "block_request_key", name="uq_card_block_key"),
        CheckConstraint("status IN ('active','blocked')", name="ck_card_status"),
        CheckConstraint("expiry_month BETWEEN 1 AND 12"),
        CheckConstraint("expiry_year BETWEEN 2000 AND 2200"),
    )

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
    catalog_service_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    service_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(String(16))
    details: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_request_owner"),
        ForeignKeyConstraint(["transaction_id","user_id"], ["transactions.id","transactions.user_id"]),
        ForeignKeyConstraint(["source_product_id","user_id"], ["products.id","products.user_id"], name="fk_requests_source_owner"),
        UniqueConstraint("user_id","transaction_id"), UniqueConstraint("user_id","request_key"),
        CheckConstraint("status IN ('received','in_review','handed_off')"),
        CheckConstraint("reason IN ('unknown','amount','payment','other')"),
        CheckConstraint("length(details) BETWEEN 10 AND 1000")
    )

class Refund(Base):
    __tablename__ = "refunds"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True)
    destination_product_id: Mapped[str] = mapped_column(String(64))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    request_key: Mapped[str] = mapped_column(String(64))
    decision_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    credit_transaction_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(["request_id", "user_id"], ["requests.id", "requests.user_id"]),
        ForeignKeyConstraint(["transaction_id", "user_id"], ["transactions.id", "transactions.user_id"]),
        ForeignKeyConstraint(["credit_transaction_id", "user_id"], ["transactions.id", "transactions.user_id"]),
        ForeignKeyConstraint(["destination_product_id", "user_id"], ["products.id", "products.user_id"]),
        UniqueConstraint("user_id", "request_key"),
        UniqueConstraint("decided_by", "decision_key"),
        CheckConstraint("amount_minor > 0 AND currency = 'MXN'"),
        CheckConstraint("status IN ('pending','approved','rejected')"),
        CheckConstraint("(status = 'pending' AND decided_by IS NULL AND decided_at IS NULL AND decision_key IS NULL AND decision_note IS NULL AND credit_transaction_id IS NULL) OR (status IN ('approved','rejected') AND decided_by IS NOT NULL AND decided_at IS NOT NULL AND decision_key IS NOT NULL AND decision_note IS NOT NULL)"),
        CheckConstraint("(status = 'approved' AND credit_transaction_id IS NOT NULL) OR (status <> 'approved' AND credit_transaction_id IS NULL)"),
    )

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    request_id: Mapped[str | None] = mapped_column(ForeignKey("requests.id"), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), nullable=True, index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (ForeignKeyConstraint(["transaction_id", "user_id"], ["transactions.id", "transactions.user_id"], name="fk_audit_transaction_owner"),)

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    locale: Mapped[str] = mapped_column(String(2))
    transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("id", "user_id"), CheckConstraint("locale IN ('es','en','pt')"), ForeignKeyConstraint(["transaction_id", "user_id"], ["transactions.id", "transactions.user_id"], name="fk_conversation_transaction_owner"))

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    document: Mapped["ChatDocument | None"] = relationship(lazy="selectin", uselist=False)
    __table_args__ = (ForeignKeyConstraint(["conversation_id", "user_id"], ["conversations.id", "conversations.user_id"]), CheckConstraint("role IN ('user','assistant')"), CheckConstraint("locale IN ('es','en','pt')"))

class PhoneBill(Base):
    __tablename__ = "phone_bills"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # Historical table name retained so existing receipts keep their references.
    service_id: Mapped[str] = mapped_column(String(64), default="phone-bill", server_default="phone-bill")
    allow_partial: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    reference: Mapped[str] = mapped_column(String(64))
    period: Mapped[str] = mapped_column(String(7))
    due_date: Mapped[str] = mapped_column(String(10))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="MXN")
    __table_args__ = (UniqueConstraint("id", "user_id"), UniqueConstraint("user_id", "service_id", "reference", "period", name="uq_bill_service_period"), CheckConstraint("amount_minor > 0 AND currency = 'MXN'"))

class BillPayment(Base):
    __tablename__ = "bill_payments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    bill_id: Mapped[str] = mapped_column(String(64), index=True)
    account_id: Mapped[str] = mapped_column(String(64))
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True)
    request_key: Mapped[str] = mapped_column(String(64))
    # Immutable receipt, independent of later changes to the bill or account.
    receipt: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (ForeignKeyConstraint(["bill_id", "user_id"], ["phone_bills.id", "phone_bills.user_id"]), ForeignKeyConstraint(["account_id", "user_id"], ["products.id", "products.user_id"]), ForeignKeyConstraint(["transaction_id", "user_id"], ["transactions.id", "transactions.user_id"]), UniqueConstraint("user_id", "request_key"))

class ConversationFlow(Base):
    __tablename__ = "conversation_flows"
    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[dict] = mapped_column(JSON)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    __table_args__ = (ForeignKeyConstraint(["conversation_id", "user_id"], ["conversations.id", "conversations.user_id"]), ForeignKeyConstraint(["request_id", "user_id"], ["requests.id", "requests.user_id"]))

class AssistantTurn(Base):
    __tablename__ = "assistant_turns"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)


class VoiceSession(Base):
    __tablename__ = 'voice_sessions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    auth_hash: Mapped[str] = mapped_column(String(64))
    request_key: Mapped[str] = mapped_column(String(64))
    provider_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default='connecting')
    locale: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[int] = mapped_column(BigInteger)
    expires_at: Mapped[int] = mapped_column(BigInteger)
    heartbeat_at: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (ForeignKeyConstraint(['conversation_id','user_id'], ['conversations.id','conversations.user_id']),
        UniqueConstraint('user_id','request_key'), CheckConstraint("status IN ('connecting','active','closing','closed','failed')"))


class TransferQuote(Base):
    __tablename__ = "transfer_quotes"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_user_id: Mapped[str] = mapped_column(String(64))
    recipient_product_id: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (ForeignKeyConstraint(["recipient_product_id", "recipient_user_id"], ["products.id", "products.user_id"]),)


class BankTransfer(Base):
    __tablename__ = "bank_transfers"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source_product_id: Mapped[str] = mapped_column(String(64))
    recipient_product_id: Mapped[str] = mapped_column(String(64))
    debit_transaction_id: Mapped[str] = mapped_column(String(64), unique=True)
    credit_transaction_id: Mapped[str] = mapped_column(String(64), unique=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    request_key: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64))
    receipt: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(["source_product_id", "user_id"], ["products.id", "products.user_id"]),
        ForeignKeyConstraint(["recipient_product_id", "recipient_user_id"], ["products.id", "products.user_id"]),
        ForeignKeyConstraint(["debit_transaction_id", "user_id"], ["transactions.id", "transactions.user_id"]),
        ForeignKeyConstraint(["credit_transaction_id", "recipient_user_id"], ["transactions.id", "transactions.user_id"]),
        UniqueConstraint("user_id", "request_key"), CheckConstraint("amount_minor > 0 AND user_id <> recipient_user_id"),
    )


class ChatDocument(Base):
    __tablename__ = "chat_documents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), unique=True)
    kind: Mapped[str] = mapped_column(String(32))
    locale: Mapped[str] = mapped_column(String(2))
    filename: Mapped[str] = mapped_column(String(100))
    request_key: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (ForeignKeyConstraint(["conversation_id", "user_id"], ["conversations.id", "conversations.user_id"]), UniqueConstraint("user_id", "request_key"))
