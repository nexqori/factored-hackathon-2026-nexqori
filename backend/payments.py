"""Local ledger payments. No external collector is connected."""
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from .models import PhoneBill, BillPayment, Product, Transaction, AuditEvent, User, now
from .schemas import ConfirmInput
from pydantic import Field
from .security import customer, customer_read, db_session
from .catalog import SERVICES


class PayBill(ConfirmInput):
    accountId: str = Field(min_length=1, max_length=64)
    requestKey: str = Field(min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")


def payment_router():
    router = APIRouter()

    @router.get('/api/phone-bills')
    def bills(user=Depends(customer_read), db=Depends(db_session)):
        payments = {p.bill_id: p for p in db.scalars(select(BillPayment).where(BillPayment.user_id == user.id))}
        rows = db.scalars(select(PhoneBill).where(PhoneBill.user_id == user.id).order_by(PhoneBill.period.desc(), PhoneBill.id))
        return {'bills': [{'id': b.id, 'reference': b.reference, 'provider': SERVICES['phone-bill']['provider'],
                           'period': b.period, 'dueDate': b.due_date, 'amountMinor': b.amount_minor, 'currency': b.currency,
                           'paymentId': payments[b.id].id if b.id in payments else None} for b in rows]}

    @router.get('/api/payments/{payment_id}')
    def receipt(payment_id: str, user=Depends(customer_read), db=Depends(db_session)):
        payment = db.scalar(select(BillPayment).where(BillPayment.id == payment_id, BillPayment.user_id == user.id))
        if not payment: raise HTTPException(404, 'not_found')
        return payment.receipt

    @router.post('/api/phone-bills/{bill_id}/pay')
    def pay(bill_id: str, body: PayBill, user=Depends(customer), db=Depends(db_session)):
        # Serialize keys per owner, then bill and account; all effects commit together.
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        bill = db.scalar(select(PhoneBill).where(PhoneBill.id == bill_id, PhoneBill.user_id == user.id).with_for_update())
        if not bill: raise HTTPException(404, 'not_found')
        previous = db.scalar(select(BillPayment).where(BillPayment.user_id == user.id, BillPayment.request_key == body.requestKey))
        if previous:
            if previous.bill_id != bill_id or previous.account_id != body.accountId: raise HTTPException(409, 'conflict')
            return previous.receipt
        previous = db.scalar(select(BillPayment).where(BillPayment.bill_id == bill_id, BillPayment.user_id == user.id))
        if previous:
            if previous.account_id != body.accountId: raise HTTPException(409, 'bill_already_paid')
            return previous.receipt
        account = db.scalar(select(Product).where(Product.id == body.accountId, Product.user_id == user.id,
                                                  Product.type.in_(('account','savings')), Product.currency == bill.currency).with_for_update())
        if not account: raise HTTPException(404, 'not_found')
        if account.balance_minor is None or account.balance_minor < bill.amount_minor: raise HTTPException(409, 'insufficient_funds')
        at = now(); payment_id = 'PAY-' + uuid4().hex[:16].upper(); transaction_id = 'TX-' + uuid4().hex[:16].upper()
        provider = SERVICES['phone-bill']['provider']
        receipt = {'id': payment_id, 'billId': bill.id, 'transactionId': transaction_id, 'provider': provider,
                   'reference': bill.reference, 'period': bill.period, 'amountMinor': bill.amount_minor,
                   'currency': bill.currency, 'accountLast4': account.last4, 'date': at.isoformat(), 'status': 'completed'}
        account.balance_minor -= bill.amount_minor
        db.add(Transaction(id=transaction_id, user_id=user.id, product_id=account.id, merchant=provider,
                           category='utilities', amount_minor=-bill.amount_minor, currency=bill.currency, occurred_at=at, status='completed'))
        db.flush()
        db.add(BillPayment(id=payment_id, user_id=user.id, bill_id=bill.id, account_id=account.id, transaction_id=transaction_id,
                           request_key=body.requestKey, receipt=receipt, created_at=at))
        db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, action='phone_bill_paid',
                          transaction_id=transaction_id, product_id=account.id, created_at=at))
        db.commit()
        return receipt

    return router


def seed_phone_bill(db):
    """Fixed, fictional monthly fixture; never infer a bill from dataset merchants."""
    account = db.get(Product, 'account-01')
    if db.get(User, 'andrea') and account and account.user_id == 'andrea' and not db.get(PhoneBill, 'phone-andrea-2026-10'):
        db.add(PhoneBill(id='phone-andrea-2026-10', user_id='andrea', reference='5500000001', period='2026-10',
                         due_date='2026-10-15', amount_minor=29900, currency='MXN'))
        db.commit()
