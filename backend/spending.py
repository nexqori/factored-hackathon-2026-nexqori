"""Owned spending comparisons and explicitly confirmed baseline exclusions."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from .models import Transaction, SpendingException, AuditEvent
from pydantic import BaseModel, ConfigDict, StrictBool
from uuid import uuid4
from .payment_history import compare_payments
from .security import customer, customer_read, db_session


def insight(db, tx):
    comparison = compare_payments(db, tx)
    classification = ('exceptional' if comparison.get('recognizedException') else 'unusual' if comparison['unusualIncrease'] else
                      'comparable' if comparison['status'] == 'sufficient' else 'limited')
    return {'transactionId': tx.id, 'classification': classification, 'comparison': comparison,
            'canRecognizeException': tx.amount_minor < 0 and tx.status == 'completed' and not comparison.get('recognizedException')}


class RecognizeException(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmed: StrictBool


def spending_router():
    router = APIRouter(prefix='/api/movements')

    @router.get('/trends')
    def trends(offset: int = Query(0, ge=0, le=100000), user=Depends(customer_read), db=Depends(db_session)):
        # A page of 40 bounds comparison work; clients can explicitly load more.
        rows = db.scalars(select(Transaction).where(Transaction.user_id == user.id,
            Transaction.amount_minor < 0).order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
            .offset(offset).limit(41)).all()
        return {'items': [insight(db, tx) for tx in rows[:40]],
                'nextOffset': offset + 40 if len(rows) > 40 else None}

    @router.get('/{transaction_id}/trend')
    def detail(transaction_id: str, user=Depends(customer_read), db=Depends(db_session)):
        tx = db.scalar(select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user.id))
        if not tx:
            raise HTTPException(404, 'not_found')
        return insight(db, tx)

    @router.post('/{transaction_id}/recognize-exception')
    def recognize(transaction_id: str, body: RecognizeException, user=Depends(customer), db=Depends(db_session)):
        if not body.confirmed:
            raise HTTPException(400, 'confirmation_required')
        tx = db.scalar(select(Transaction).where(Transaction.id == transaction_id,
            Transaction.user_id == user.id).with_for_update())
        if not tx:
            raise HTTPException(404, 'not_found')
        if tx.amount_minor >= 0 or tx.status != 'completed':
            raise HTTPException(409, 'operation_not_allowed')
        existing = db.scalar(select(SpendingException).where(
            SpendingException.transaction_id == tx.id, SpendingException.user_id == user.id))
        if not existing:
            db.add(SpendingException(transaction_id=tx.id, user_id=user.id))
            db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id,
                transaction_id=tx.id, action='spending_exception_confirmed'))
            db.flush()
        result = insight(db, tx)
        db.commit()
        return result

    return router
