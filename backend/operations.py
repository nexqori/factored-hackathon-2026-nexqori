"""Authenticated local operations. The LAB/model has no authority in this router."""
from typing import Literal
from uuid import uuid4
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .models import ClaimReview, AuditEvent, CardProfile, Product, Refund, RequestCase, Transaction, User, NotificationPreference, now
from .schemas import ConfirmInput
from .workflows import WORKFLOWS
from .security import admin, admin_write, customer, customer_read, current_session, db_session, LoginLimiter, verify
from .notifications import email_required, consume_code


class OperationInput(ConfirmInput):
    requestKey: str = Field(min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")


class BlockInput(OperationInput):
    password: str = Field(min_length=1, max_length=256)


class CardBlockInput(BlockInput):
    challengeId: str | None = Field(default=None, max_length=64)
    code: str | None = Field(default=None, pattern=r'^\d{6}$')


class DecisionInput(BlockInput):
    decision: Literal["approve", "reject"]
    note: str = Field(min_length=10, max_length=1000)


def audit(db, owner, actor, action, case=None, product=None):
    db.add(AuditEvent(id=str(uuid4()), user_id=owner, actor_id=actor, action=action,
                      request_id=case, product_id=product))


def iso_utc(value):
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()


def refund_view(db, refund):
    account = db.get(Product, refund.destination_product_id)
    return {"id": refund.id, "requestId": refund.request_id, "transactionId": refund.transaction_id,
            "amountMinor": refund.amount_minor, "currency": refund.currency,
            "destinationLast4": account.last4, "status": refund.status,
            "decisionNote": refund.decision_note, "creditTransactionId": refund.credit_transaction_id,
            "createdAt": iso_utc(refund.created_at),
            "decidedAt": iso_utc(refund.decided_at) if refund.decided_at else None}


def refund_source(db, case, lock=False):
    # A query or unrelated request can never become a refund instruction.
    if not ("request-refund" in WORKFLOWS.get(case.catalog_service_id, {}).get("availableActions", [])
            or (case.catalog_service_id is None and case.reason in {"unknown", "amount", "payment"})):
        raise HTTPException(409, "refund_not_eligible")
    query = select(Transaction).where(Transaction.id == case.transaction_id, Transaction.user_id == case.user_id)
    tx = db.scalar(query.with_for_update() if lock else query)
    if not tx or tx.status != "completed" or tx.amount_minor >= 0 or tx.category == "refund":
        raise HTTPException(409, "refund_not_eligible")
    source = db.scalar(select(Product).where(Product.id == tx.product_id, Product.user_id == case.user_id))
    destination_id = source.id
    if source.type == "card":
        card = db.scalar(select(CardProfile).where(CardProfile.product_id == source.id, CardProfile.user_id == case.user_id))
        destination_id = card.settlement_product_id if card else None
    query = select(Product).where(Product.id == destination_id, Product.user_id == case.user_id,
                                 Product.type.in_(["account", "savings"]))
    destination = db.scalar(query.with_for_update() if lock else query)
    if not destination or destination.balance_minor is None or destination.currency != tx.currency:
        raise HTTPException(409, "refund_destination_unavailable")
    return tx, destination


def refund_state(db, case):
    existing = db.scalar(select(Refund).where(Refund.request_id == case.id, Refund.user_id == case.user_id))
    if existing:
        return {"eligible": False, "refund": refund_view(db, existing), "preview": None, "reason": None}
    try:
        tx, destination = refund_source(db, case)
        return {"eligible": True, "refund": None, "reason": None, "preview": {
            "transactionId": tx.id, "merchant": tx.merchant, "amountMinor": -tx.amount_minor,
            "currency": tx.currency, "destinationLast4": destination.last4}}
    except HTTPException as exc:
        return {"eligible": False, "refund": None, "preview": None, "reason": exc.detail}


def operations_router():
    router = APIRouter(prefix="/api")
    limiter = LoginLimiter(8)

    def reauthenticate(request, user, password):
        limiter.consume(request.client.host if request.client else "local", user.id)
        if not verify(password, user.password_hash):
            raise HTTPException(403, "card_password")

    @router.post("/cards/{product_id}/block")
    def block(product_id: str, payload: CardBlockInput, request: Request, user=Depends(customer), auth=Depends(current_session), db=Depends(db_session)):
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        card = db.scalar(select(CardProfile).where(CardProfile.product_id == product_id, CardProfile.user_id == user.id).with_for_update())
        if not card:
            raise HTTPException(404, "not_found")
        reauthenticate(request, user, payload.password)
        used = db.scalar(select(CardProfile).where(CardProfile.user_id == user.id, CardProfile.block_request_key == payload.requestKey))
        if used and used.product_id != card.product_id:
            raise HTTPException(409, "idempotency_conflict")
        if card.status != "blocked":
            if email_required():
                setting = db.get(NotificationPreference, user.id)
                if not setting:
                    raise HTTPException(409, 'notification_email_required')
                code = consume_code(db, user, auth[0], payload.challengeId, payload.code, 'card_block', card.product_id)
                if code.email != setting.email:
                    raise HTTPException(403, 'email_code_invalid')
            card.status = "blocked"
            card.blocked_at = now()
            card.block_request_key = payload.requestKey
            audit(db, user.id, user.id, "card_blocked", product=card.product_id)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(409, "idempotency_conflict")
        return {"id": card.product_id, "status": card.status, "blockedAt": iso_utc(card.blocked_at)}

    def own_case(db, case_id, user, lock=False):
        query = select(RequestCase).where(RequestCase.id == case_id, RequestCase.user_id == user.id)
        case = db.scalar(query.with_for_update() if lock else query)
        if not case:
            raise HTTPException(404, "not_found")
        return case

    @router.get("/requests/{case_id}/refund")
    def preview(case_id: str, user=Depends(customer_read), db=Depends(db_session)):
        return refund_state(db, own_case(db, case_id, user))

    @router.get("/admin/requests/{case_id}/refund")
    def admin_preview(case_id: str, _user=Depends(admin), db=Depends(db_session)):
        case = db.get(RequestCase, case_id)
        if not case:
            raise HTTPException(404, "not_found")
        state = refund_state(db, case)
        review = db.get(ClaimReview, case.id)
        return {**state, 'claimApproved': bool(review and review.stage == 'approved')}

    @router.post("/requests/{case_id}/refund")
    def request_refund(case_id: str, payload: OperationInput, user=Depends(customer), db=Depends(db_session)):
        case = own_case(db, case_id, user, lock=True)
        used = db.scalar(select(Refund).where(Refund.user_id == user.id, Refund.request_key == payload.requestKey))
        if used and used.request_id != case.id:
            raise HTTPException(409, "idempotency_conflict")
        existing = db.scalar(select(Refund).where(Refund.request_id == case.id, Refund.user_id == user.id))
        if existing:
            return refund_view(db, existing)
        tx, destination = refund_source(db, case, lock=True)
        refund = Refund(id="RF-" + str(uuid4()), user_id=user.id, request_id=case.id, transaction_id=tx.id,
                        destination_product_id=destination.id, amount_minor=-tx.amount_minor,
                        currency=tx.currency, request_key=payload.requestKey, status="pending")
        db.add(refund)
        audit(db, user.id, user.id, "refund_requested", case=case.id, product=destination.id)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "idempotency_conflict")
        return refund_view(db, refund)

    @router.post("/admin/refunds/{refund_id}/decision")
    def decision(refund_id: str, payload: DecisionInput, request: Request, user=Depends(admin_write), db=Depends(db_session)):
        refund = db.scalar(select(Refund).where(Refund.id == refund_id).with_for_update())
        if not refund:
            raise HTTPException(404, "not_found")
        reauthenticate(request, user, payload.password)
        note = payload.note.strip()
        if len(note) < 10:
            raise HTTPException(422, "details")
        final = "approved" if payload.decision == "approve" else "rejected"
        if refund.status != "pending":
            if (refund.status == final and refund.decision_key == payload.requestKey
                    and refund.decided_by == user.id and refund.decision_note == note):
                return refund_view(db, refund)
            raise HTTPException(409, "refund_already_decided")
        used = db.scalar(select(Refund).where(Refund.decided_by == user.id, Refund.decision_key == payload.requestKey))
        if used:
            raise HTTPException(409, "idempotency_conflict")
        if final == "approved":
            review = db.get(ClaimReview, refund.request_id)
            if not review or review.user_id != refund.user_id or review.stage != 'approved':
                raise HTTPException(409, 'claim_approval_required')
            case = db.scalar(select(RequestCase).where(RequestCase.id == refund.request_id, RequestCase.user_id == refund.user_id))
            tx, destination = refund_source(db, case, lock=True)
            if (tx.id != refund.transaction_id or destination.id != refund.destination_product_id
                    or -tx.amount_minor != refund.amount_minor or tx.currency != refund.currency):
                raise HTTPException(409, "refund_changed")
            credit = Transaction(id="CR-" + str(uuid4()), user_id=refund.user_id, product_id=destination.id,
                                 merchant=("Nexqori · " + tx.merchant)[:150], category="refund", amount_minor=refund.amount_minor,
                                 currency=refund.currency, occurred_at=now(), status="completed")
            db.add(credit)
            db.flush()
            destination.balance_minor += refund.amount_minor
            refund.credit_transaction_id = credit.id
        refund.status = final
        refund.decision_note = note
        refund.decision_key = payload.requestKey
        refund.decided_by = user.id
        refund.decided_at = now()
        audit(db, refund.user_id, user.id, "refund_approved" if final == "approved" else "refund_rejected",
              case=refund.request_id, product=refund.destination_product_id)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "idempotency_conflict")
        return refund_view(db, refund)

    return router
