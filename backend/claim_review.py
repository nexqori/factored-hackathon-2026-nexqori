"""Administrative milestones do not credit money or execute model proposals."""
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .catalog import request_kind
from .models import ClaimReview, Refund, RequestCase, now, iso_utc
from .schemas import ConfirmInput
from .security import admin_write, db_session

STAGES = ('received', 'delivered', 'in_review', 'approved')


class StageInput(ConfirmInput):
    stage: Literal['delivered', 'in_review', 'approved']
    note: str = Field(default='', max_length=1000)


def handling_view(case):
    if request_kind(case) != 'claim':
        return None
    row = case.handling
    return {'stage': row.stage if row else ('in_review' if case.status == 'in_review' else 'received'),
            'note': row.note if row else None,
            'updatedAt': iso_utc(row.updated_at) if row else None}


def advance(db, case, user, body):
    from .operations import refund_source, audit
    if request_kind(case) != 'claim':
        raise HTTPException(409, 'claim_only')
    row = db.get(ClaimReview, case.id)
    current = row.stage if row else ('in_review' if case.status == 'in_review' else 'received')
    target = body.stage
    note = body.note.strip()
    if target == 'approved' and len(note) < 10:
        raise HTTPException(422, 'details')
    if STAGES.index(target) <= STAGES.index(current):
        if target == 'approved' and row and note != row.note:
            raise HTTPException(409, 'invalid_transition')
        return handling_view(case)
    if STAGES.index(target) != STAGES.index(current) + 1:
        raise HTTPException(409, 'invalid_transition')
    refund = db.scalar(select(Refund).where(Refund.request_id == case.id))
    if refund and refund.status != 'pending':
        raise HTTPException(409, 'refund_already_decided')
    timestamp = now()
    if not row:
        row = ClaimReview(request_id=case.id, user_id=case.user_id, stage=target, actor_id=user.id)
        db.add(row)
        case.handling = row
    row.stage, row.actor_id, row.updated_at = target, user.id, timestamp
    if target == 'approved':
        row.note = note
        # Approval prepares an eligible refund for a separate, password-confirmed
        # action. A pending/declined transaction never becomes a credit.
        if not refund:
            try:
                tx, destination = refund_source(db, case, lock=True)
            except HTTPException as error:
                if error.status_code != 409:
                    raise
            else:
                refund = Refund(id='RF-'+str(uuid4()), user_id=case.user_id, request_id=case.id,
                    transaction_id=tx.id, destination_product_id=destination.id,
                    amount_minor=-tx.amount_minor, currency=tx.currency,
                    request_key='admin-review-'+str(uuid4()), status='pending')
                db.add(refund)
                audit(db, case.user_id, user.id, 'refund_requested', case=case.id, product=destination.id)
    if target == 'in_review':
        case.status = 'in_review'
    case.updated_at = timestamp
    audit(db, case.user_id, user.id, {'delivered':'claim_delivered', 'in_review':'reviewed', 'approved':'claim_approved'}[target], case=case.id)
    return handling_view(case)


def claim_review_router():
    router = APIRouter(prefix='/api')

    @router.post('/admin/requests/{request_id}/stage')
    def stage(request_id: str, body: StageInput, user=Depends(admin_write), db=Depends(db_session)):
        case = db.scalar(select(RequestCase).where(RequestCase.id == request_id).with_for_update())
        if not case:
            raise HTTPException(404, 'not_found')
        try:
            result = advance(db, case, user, body)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'idempotency_conflict') from None
        return {'handling': result}

    return router
