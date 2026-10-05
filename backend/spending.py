"""Read-only views of the same comparisons used by the authenticated chat."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from .models import Transaction
from .payment_history import compare_payments
from .security import customer_read, db_session


def insight(db, tx):
    comparison = compare_payments(db, tx)
    classification = ('unusual' if comparison['unusualIncrease'] else
                      'comparable' if comparison['status'] == 'sufficient' else 'limited')
    return {'transactionId': tx.id, 'classification': classification, 'comparison': comparison}


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

    return router
