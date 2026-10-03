"""Local ledger payments. No external collector is connected."""
import hashlib
import json
import re
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from .models import PhoneBill, BillPayment, Product, Transaction, AuditEvent, User, now
from .schemas import ConfirmInput
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .security import customer, customer_read, db_session
from .catalog import SERVICES


class PayBill(ConfirmInput):
    accountId: str = Field(min_length=1, max_length=64)
    requestKey: str = Field(min_length=16, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")


class BillLookup(BaseModel):
    model_config = ConfigDict(extra='forbid')
    serviceId: str = Field(min_length=1, max_length=64)
    reference: str = Field(min_length=3, max_length=64)


class ServicePayment(PayBill):
    mode: Literal['total','partial'] = 'total'
    # This selects a supported local processing path, never an arbitrary status.
    processingMode: Literal['immediate','pending'] = 'immediate'
    amountMinor: int | None = Field(default=None, strict=True, gt=0, le=100_000_000)
    expectedOutstandingMinor: int = Field(strict=True, gt=0)

    @model_validator(mode='after')
    def amount_choice(self):
        if (self.mode == 'partial') != (self.amountMinor is not None):
            raise ValueError('Only a partial payment accepts an amount.')
        return self


def fingerprint(body):
    values = body.model_dump(exclude={'requestKey'})
    # Immediate is the historical behavior. Preserve fingerprints of receipts
    # created before this optional field existed, including lost-response retries.
    if values.get('processingMode') == 'immediate':
        values.pop('processingMode')
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def bill_view(db, bill):
    rows = db.scalars(select(BillPayment).where(BillPayment.bill_id == bill.id, BillPayment.user_id == bill.user_id).order_by(BillPayment.created_at, BillPayment.id)).all()
    pending_rows = [p for p in rows if p.receipt.get('status') == 'pending']
    paid = sum(p.receipt['amountMinor'] for p in rows if p.receipt.get('status', 'completed') == 'completed')
    pending = sum(p.receipt['amountMinor'] for p in pending_rows)
    outstanding = max(0, bill.amount_minor-paid-pending)
    status = 'pending' if pending else 'completed' if outstanding == 0 else 'partial' if paid else 'unpaid'
    return {'id': bill.id, 'serviceId': bill.service_id, 'reference': bill.reference,
            'provider': SERVICES[bill.service_id]['provider'], 'period': bill.period, 'dueDate': bill.due_date,
            'amountMinor': bill.amount_minor, 'paidMinor': paid, 'pendingMinor': pending, 'outstandingMinor': outstanding,
            'paymentStatus': status, 'pendingPaymentId': pending_rows[-1].id if pending_rows else None,
            'processingOptions': ['immediate', 'pending'] if bill.service_id == 'phone-bill' else ['immediate'],
            'allowPartial': bill.allow_partial, 'currency': bill.currency,
            'paymentId': rows[-1].id if rows and outstanding == 0 else None}


def pay_bill(db, user, bill_id, body, *, legacy=False):
    # Every debit, receipt and audit entry belongs to one atomic transaction.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    bill = db.scalar(select(PhoneBill).where(PhoneBill.id == bill_id, PhoneBill.user_id == user.id).with_for_update())
    if not bill or (legacy and bill.service_id != 'phone-bill'): raise HTTPException(404, 'not_found')
    previous = db.scalar(select(BillPayment).where(BillPayment.user_id == user.id, BillPayment.request_key == body.requestKey))
    digest = fingerprint(body)
    if previous:
        if previous.bill_id != bill_id or previous.account_id != body.accountId or (previous.fingerprint and previous.fingerprint != digest):
            raise HTTPException(409, 'conflict')
        return previous.receipt
    pending = not legacy and body.processingMode == 'pending'
    # All receipts here belong to the local fixture ledger, without a collector.
    # Only the telephone path offers this explicit test scenario.
    if pending and bill.service_id != 'phone-bill': raise HTTPException(422, 'processing_not_available')
    view = bill_view(db, bill)
    if view['outstandingMinor'] == 0:
        if legacy:
            previous = db.get(BillPayment, view['paymentId'])
            if previous.account_id == body.accountId: return previous.receipt
        raise HTTPException(409, 'bill_in_processing' if view['pendingMinor'] else 'bill_already_paid')
    if not legacy and body.expectedOutstandingMinor != view['outstandingMinor']: raise HTTPException(409, 'bill_changed')
    partial = not legacy and body.mode == 'partial'
    if partial and not bill.allow_partial: raise HTTPException(422, 'partial_not_allowed')
    amount = body.amountMinor if partial else view['outstandingMinor']
    if amount > view['outstandingMinor']: raise HTTPException(422, 'payment_exceeds_bill')
    account = db.scalar(select(Product).where(Product.id == body.accountId, Product.user_id == user.id,
                                              Product.type.in_(('account','savings')), Product.currency == bill.currency).with_for_update())
    if not account: raise HTTPException(404, 'not_found')
    if account.balance_minor is None or account.balance_minor < amount: raise HTTPException(409, 'insufficient_funds')
    status = 'pending' if pending else 'completed'
    at = now(); payment_id = 'PAY-' + uuid4().hex[:16].upper(); transaction_id = 'TX-' + uuid4().hex[:16].upper()
    receipt = {'id': payment_id, 'billId': bill.id, 'transactionId': transaction_id,
               'serviceId': bill.service_id, 'provider': view['provider'], 'reference': bill.reference, 'period': bill.period,
               'amountMinor': amount, 'billAmountMinor': bill.amount_minor, 'remainingMinor': view['outstandingMinor']-amount,
               'currency': bill.currency, 'accountLast4': account.last4, 'date': at.isoformat(), 'status': status}
    account.balance_minor -= amount
    db.add(Transaction(id=transaction_id, user_id=user.id, product_id=account.id, merchant=view['provider'],
                       category='utilities', amount_minor=-amount, currency=bill.currency, occurred_at=at, status=status))
    db.flush()
    db.add(BillPayment(id=payment_id, user_id=user.id, bill_id=bill.id, account_id=account.id, transaction_id=transaction_id,
                       request_key=body.requestKey, fingerprint=digest, receipt=receipt, created_at=at))
    db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id,
                      action='phone_bill_pending' if pending else 'phone_bill_paid' if bill.service_id == 'phone-bill' else 'service_bill_paid',
                      transaction_id=transaction_id, product_id=account.id, created_at=at))
    db.commit()
    return receipt


def payment_router():
    router = APIRouter()

    @router.get('/api/phone-bills')
    def bills(user=Depends(customer_read), db=Depends(db_session)):
        rows = db.scalars(select(PhoneBill).where(PhoneBill.user_id == user.id, PhoneBill.service_id == 'phone-bill').order_by(PhoneBill.period.desc(), PhoneBill.id))
        return {'bills': [bill_view(db, b) for b in rows]}

    @router.get('/api/service-bills/references')
    def references(user=Depends(customer_read), db=Depends(db_session)):
        rows = db.execute(select(PhoneBill.service_id, PhoneBill.reference).where(PhoneBill.user_id == user.id).distinct().order_by(PhoneBill.service_id, PhoneBill.reference)).all()
        return {'references': [{'serviceId': s, 'reference': r} for s,r in rows]}

    @router.post('/api/service-bills/lookup')
    def lookup(body: BillLookup, user=Depends(customer), db=Depends(db_session)):
        service = SERVICES.get(body.serviceId)
        if not service or service['kind'] != 'bill': raise HTTPException(404, 'not_found')
        reference = body.reference.strip().upper()
        if service['referenceKind'] == 'phone': reference = re.sub(r'[ ()+-]', '', reference)
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9./-]{2,63}', reference): raise HTTPException(422, 'service_reference')
        rows = db.scalars(select(PhoneBill).where(PhoneBill.user_id == user.id, PhoneBill.service_id == body.serviceId,
                                                PhoneBill.reference == reference).order_by(PhoneBill.period, PhoneBill.id)).all()
        result = {'bills': [bill_view(db, b) for b in rows]}
        db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, action='service_bills_consulted'))
        db.commit()
        return result

    @router.post('/api/service-bills/{bill_id}/pay')
    def service_pay(bill_id: str, body: ServicePayment, user=Depends(customer), db=Depends(db_session)):
        return pay_bill(db, user, bill_id, body)

    @router.get('/api/payments/{payment_id}')
    def receipt(payment_id: str, user=Depends(customer_read), db=Depends(db_session)):
        payment = db.scalar(select(BillPayment).where(BillPayment.id == payment_id, BillPayment.user_id == user.id))
        if not payment: raise HTTPException(404, 'not_found')
        return payment.receipt

    @router.post('/api/phone-bills/{bill_id}/pay')
    def pay(bill_id: str, body: PayBill, user=Depends(customer), db=Depends(db_session)):
        return pay_bill(db, user, bill_id, body, legacy=True)

    return router


def seed_phone_bill(db):
    """Fixed, fictional monthly fixture; never infer a bill from dataset merchants."""
    account = db.get(Product, 'account-01')
    if db.get(User, 'andrea') and account and account.user_id == 'andrea' and not db.get(PhoneBill, 'phone-andrea-2026-10'):
        db.add(PhoneBill(id='phone-andrea-2026-10', user_id='andrea', reference='5500000001', period='2026-10',
                         due_date='2026-10-15', amount_minor=29900, currency='MXN'))
        db.commit()


def seed_service_bills(db):
    """Curated local receipts. Re-running never replenishes or edits a paid bill."""
    seed_phone_bill(db)
    if not db.get(User, 'andrea'): return
    fixtures = [('phone-family-2026-10','phone-bill','5500000002',19900,True),
                ('internet-andrea-2026-10','internet-bill','INT-4821001',45900,True),
                ('tv-andrea-2026-10','tv-bill','TV-4821001',24900,False),
                ('utilities-andrea-2026-10','utilities-bill','LUZ-4821001',52000,True)]
    for ident,service,reference,amount,partial in fixtures:
        if not db.get(PhoneBill,ident):
            db.add(PhoneBill(id=ident,user_id='andrea',service_id=service,reference=reference,period='2026-10',
                             due_date='2026-10-20',amount_minor=amount,allow_partial=partial))
    db.commit()
