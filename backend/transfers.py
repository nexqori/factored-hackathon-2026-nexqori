"""Confirmed transfers inside the local Nexqori ledger, never an external rail."""
import secrets
import time
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select, or_
from .models import User, Product, TransferQuote, BankTransfer, Transaction, AuditEvent, now
from .schemas import StrictModel, ConfirmInput
from .security import customer, customer_read, db_session, LoginLimiter
from .payments import fingerprint


class RecipientLookup(StrictModel):
    reference: str = Field(pattern=r'^\d{12,18}$')


class TransferInput(ConfirmInput):
    quoteId: str = Field(min_length=1, max_length=64)
    accountId: str = Field(min_length=1, max_length=64)
    amountMinor: int = Field(gt=0, le=100_000_000)
    note: str = Field(default='', max_length=140)
    requestKey: str = Field(min_length=16, max_length=64, pattern=r'^[a-zA-Z0-9-]+$')


def assign_account_references(db):
    known = {'account-01': '700000000000004821', 'savings-01': '700000000000007206', 'account-02': '700000000000001103'}
    for p in db.scalars(select(Product).where(Product.type.in_(('account','savings')), Product.transfer_reference.is_(None))):
        p.transfer_reference = known.get(p.id) or '7' + str(secrets.randbelow(10**17)).zfill(17)
    db.commit()


def transfer_router():
    router = APIRouter(); limiter = LoginLimiter(limit=15)

    @router.post('/api/transfers/recipient')
    def recipient(body: RecipientLookup, user=Depends(customer), db=Depends(db_session)):
        limiter.consume('transfer-'+user.id, user.id)
        result = db.execute(select(Product, User).join(User, User.id == Product.user_id).where(
            Product.transfer_reference == body.reference, Product.type.in_(('account','savings')),
            Product.currency == 'MXN', User.role == 'customer', User.id != user.id)).first()
        if not result: raise HTTPException(404, 'recipient_not_found')
        product, target = result
        quote = TransferQuote(id=str(uuid4()), user_id=user.id, recipient_user_id=target.id,
                              recipient_product_id=product.id, expires_at=int(time.time())+600)
        db.add(quote); db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, action='transfer_recipient_checked'))
        db.commit()
        return {'quoteId': quote.id, 'name': target.name, 'reference': product.transfer_reference,
                'last4': product.last4, 'currency': product.currency, 'expiresAt': quote.expires_at}

    @router.post('/api/transfers')
    def transfer(body: TransferInput, user=Depends(customer), db=Depends(db_session)):
        quote = db.scalar(select(TransferQuote).where(TransferQuote.id == body.quoteId, TransferQuote.user_id == user.id))
        if not quote: raise HTTPException(404, 'not_found')
        # Consistent owner and account ordering prevents A→B / B→A deadlocks.
        owners = db.scalars(select(User).where(User.id.in_((user.id, quote.recipient_user_id))).order_by(User.id).with_for_update()).all()
        previous = db.scalar(select(BankTransfer).where(BankTransfer.user_id == user.id, BankTransfer.request_key == body.requestKey))
        digest = fingerprint(body)
        if previous:
            if previous.fingerprint != digest: raise HTTPException(409, 'conflict')
            return previous.receipt
        if quote.expires_at <= int(time.time()): raise HTTPException(409, 'recipient_expired')
        if len(owners) != 2 or any(o.role != 'customer' for o in owners): raise HTTPException(404, 'not_found')
        accounts = {p.id:p for p in db.scalars(select(Product).where(Product.id.in_((body.accountId, quote.recipient_product_id))).order_by(Product.id).with_for_update())}
        source, target = accounts.get(body.accountId), accounts.get(quote.recipient_product_id)
        if not source or not target or source.user_id != user.id or target.user_id != quote.recipient_user_id or source.user_id == target.user_id:
            raise HTTPException(404, 'not_found')
        if any(p.type not in ('account','savings') or p.currency != 'MXN' or p.balance_minor is None for p in (source,target)):
            raise HTTPException(422, 'transfer_account')
        if source.balance_minor < body.amountMinor: raise HTTPException(409, 'insufficient_funds')
        names = {o.id:o.name for o in owners}; at = now()
        ident, debit, credit = ['TRF-'+uuid4().hex[:16].upper(), 'TX-'+uuid4().hex[:16].upper(), 'TX-'+uuid4().hex[:16].upper()]
        source.balance_minor -= body.amountMinor; target.balance_minor += body.amountMinor
        db.add_all([
            Transaction(id=debit, user_id=user.id, product_id=source.id, merchant=names[target.user_id], category='transfer', amount_minor=-body.amountMinor, currency='MXN', occurred_at=at, status='completed'),
            Transaction(id=credit, user_id=target.user_id, product_id=target.id, merchant=names[user.id], category='transfer', amount_minor=body.amountMinor, currency='MXN', occurred_at=at, status='completed')])
        db.flush()
        receipt = {'id':ident, 'status':'completed', 'amountMinor':body.amountMinor, 'currency':'MXN', 'date':at.isoformat(),
                   'senderName':names[user.id], 'recipientName':names[target.user_id], 'accountLast4':source.last4,
                   'recipientLast4':target.last4, 'note':body.note.strip(), 'transactionId':debit}
        db.add(BankTransfer(id=ident,user_id=user.id,recipient_user_id=target.user_id,source_product_id=source.id,
                            recipient_product_id=target.id,debit_transaction_id=debit,credit_transaction_id=credit,
                            amount_minor=body.amountMinor,request_key=body.requestKey,fingerprint=digest,receipt=receipt,created_at=at))
        for owner,pid,tx,action in ((user.id,source.id,debit,'transfer_sent'),(target.user_id,target.id,credit,'transfer_received')):
            db.add(AuditEvent(id=str(uuid4()),user_id=owner,actor_id=user.id,product_id=pid,transaction_id=tx,action=action))
        db.commit()
        return receipt

    @router.get('/api/transfers/{transfer_id}')
    def receipt(transfer_id: str, user=Depends(customer_read), db=Depends(db_session)):
        row = db.scalar(select(BankTransfer).where(BankTransfer.id == transfer_id, or_(BankTransfer.user_id == user.id, BankTransfer.recipient_user_id == user.id)))
        if not row: raise HTTPException(404, 'not_found')
        return {**row.receipt, 'direction':'sent' if row.user_id == user.id else 'received',
                'transactionId':row.debit_transaction_id if row.user_id == user.id else row.credit_transaction_id}

    return router
