"""Opt-in persistent UX records. Imported functions never read production config.

Run as a module only in explicit local Compose. Passwords arrive on stdin from
the private host manifest; no password is logged or returned by this module.
"""
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.engine import make_url

from .models import (User, Product, CustomerProfile, CardProfile, Transaction, PhoneBill,
                     BillPayment, BankTransfer, RequestCase, Refund, AuditEvent)
from .security import hasher

CASES = json.loads(Path(__file__).with_name('ux_scenarios.json').read_text(encoding='utf-8'))['cases']
ZONE = ZoneInfo('America/Mexico_City')


def manifest_plan(manifest):
    if set(manifest) != {'schemaVersion', 'packId', 'runId', 'createdAt', 'passwords'} or manifest['schemaVersion'] != 1:
        raise ValueError('Invalid UX manifest')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,39}', manifest['packId']) or not re.fullmatch(r'[a-f0-9]{12}', manifest['runId']):
        raise ValueError('Invalid UX package identifier')
    if set(manifest['passwords']) != {case['id'] for case in CASES} or any(
        not isinstance(p, str) or not 24 <= len(p) <= 128 for p in manifest['passwords'].values()
    ):
        raise ValueError('Five generated passwords are required')
    stamp = datetime.fromisoformat(manifest['createdAt'].replace('Z', '+00:00'))
    if stamp.tzinfo is None: raise ValueError('A timestamp with timezone is required')
    stamp = stamp.astimezone(timezone.utc)
    anchor = stamp.astimezone(ZONE)
    month_start = anchor.date().replace(day=1)
    previous_month = (month_start-timedelta(days=1)).replace(day=1)
    month_end = month_start-timedelta(days=1)
    rows = []
    for index, case in enumerate(CASES):
        suffix = manifest['runId']+'-'+case['id']
        def reference(kind):
            return '7'+str(int(hashlib.sha256((suffix+kind).encode()).hexdigest(), 16) % 10**17).zfill(17)
        phone = '55'+str(int(hashlib.sha256(suffix.encode()).hexdigest(), 16) % 10**8).zfill(8)
        account, savings, card = ('ux-'+kind+'-'+suffix for kind in ('account', 'savings', 'card'))
        def at(day): return datetime.combine(day, datetime.min.time().replace(hour=12), ZONE).astimezone(timezone.utc)
        txs = [
            {'id': 'UX-TX-SALARY-'+suffix, 'productId': account, 'merchant': 'Ingreso mensual', 'category': 'income', 'amountMinor': 220000, 'status': 'completed', 'date': at(previous_month+timedelta(days=2))},
            {'id': 'UX-TX-NET-'+suffix, 'productId': account, 'merchant': 'Internet Plus', 'category': 'utilities', 'amountMinor': -45900, 'status': 'completed', 'date': at(previous_month+timedelta(days=13))},
            {'id': 'UX-TX-TV-'+suffix, 'productId': card, 'merchant': 'Cable TV', 'category': 'utilities', 'amountMinor': -24900, 'status': 'completed', 'date': at(month_end)},
            {'id': 'UX-TX-ALT-'+suffix, 'productId': card, 'merchant': 'Servicios Públicos', 'category': 'utilities', 'amountMinor': -9900, 'status': 'completed', 'date': stamp-timedelta(days=2)},
            {'id': 'UX-TX-CASE-'+suffix, 'productId': card if case['product'] == 'card' else account,
             'merchant': case['merchant'], 'category': 'utilities', 'amountMinor': -case['amountMinor'],
             'status': case['status'], 'date': stamp-timedelta(hours=1)},
        ]
        bills = [{'id': 'ux-bill-'+key+'-'+suffix, 'serviceId': service, 'reference': ref,
                  'amountMinor': amount, 'allowPartial': partial, 'period': month_start.strftime('%Y-%m'),
                  'dueDate': month_start.replace(day=20).isoformat()}
                 for key, service, ref, amount, partial in [
                     ('phone', 'phone-bill', phone, 29900, False),
                     ('second', 'phone-bill', str(int(phone)+1), 19900, True),
                     ('net', 'internet-bill', 'INT-'+suffix.upper(), 45900, True),
                     ('tv', 'tv-bill', 'TV-'+suffix.upper(), 24900, False)]]
        rows.append({'case': case, 'userId': 'ux-user-'+suffix, 'email': 'ux-'+suffix+'@nexqori.com',
                     'identityNumber': 'UX'+manifest['runId'].upper()+str(index+1),
                     'accountId': account, 'savingsId': savings, 'cardId': card,
                     'accountReference': reference('account'), 'savingsReference': reference('savings'),
                     'accountLast4': str(9700+index*2), 'savingsLast4': str(9701+index*2),
                     'last4': str(8100+index), 'transactions': txs, 'transactionId': txs[-1]['id'],
                     'alternateTransactionId': txs[-2]['id'], 'bills': bills,
                     'balanceMinor': 150000+sum(t['amountMinor'] for t in txs if t['productId'] == account and t['status'] in ('completed', 'pending')),
                     'previousMonth': {'startDate': previous_month.isoformat(), 'endDate': month_end.isoformat()},
                     'createdAt': stamp})
    return rows


def other_records_hash(db, owners):
    result = hashlib.sha256()
    for model in (User, Product, CustomerProfile, CardProfile, Transaction, PhoneBill, BillPayment, BankTransfer, RequestCase, Refund):
        table = model.__table__
        owner = table.c.id if model is User else table.c.user_id
        result.update(table.name.encode())
        query = select(table).where(owner.not_in(owners)).order_by(*table.primary_key.columns)
        for row in db.execute(query).yield_per(500):
            result.update(json.dumps(list(row), sort_keys=True, default=str).encode())
            result.update(b'\n')
    return result.hexdigest()


def ensure_pack(db, manifest):
    """One atomic insertion or a read-only repeat. The caller commits/rolls back."""
    return ensure_profiles(db, manifest, manifest_plan(manifest))


def ensure_profiles(db, manifest, plan):
    """Persist a validated fixture plan. Only local preparation commands call this."""
    owners = [p['userId'] for p in plan]
    before = other_records_hash(db, owners)
    existing = db.scalars(select(User).where(User.id.in_(owners))).all()
    if existing:
        if len(existing) != len(plan): raise ValueError('Incomplete UX package; inspect without resetting it')
        for row in plan:
            marker = db.get(AuditEvent, 'ux-created-'+manifest['runId']+'-'+row['case']['id'])
            if not marker or marker.user_id != row['userId'] or marker.action != 'ux_fixture_created':
                raise ValueError('Existing owner does not belong to this UX package')
            for model, key in [(Product, 'accountId'), (Product, 'savingsId'), (Product, 'cardId')]:
                record = db.get(model, row[key])
                if not record or record.user_id != row['userId']: raise ValueError('Unexpected UX record owner')
    else:
        for row in plan:
            case = row['case']; uid = row['userId']; stamp = row['createdAt']
            db.add(User(id=uid, name=case['name'], email=row['email'], identity_number=row['identityNumber'],
                        password_hash=hasher.hash(manifest['passwords'][case['id']]), role='customer', locale='es', created_at=stamp))
            db.flush()
            db.add(CustomerProfile(user_id=uid, birth_date=date.fromisoformat(case['birthDate']),
                                   banking_experience=case['experience'], digital_experience=case['digital'],
                                   assistance='auto', created_at=stamp, updated_at=stamp))
            db.add_all([Product(id=row['accountId'], user_id=uid, type='account', last4=row['accountLast4'],
                                balance_minor=row['balanceMinor'], transfer_reference=row['accountReference']),
                        Product(id=row['savingsId'], user_id=uid, type='savings', last4=row['savingsLast4'], balance_minor=64000,
                                transfer_reference=row['savingsReference']),
                        Product(id=row['cardId'], user_id=uid, type='card', last4=row['last4'], balance_minor=None)])
            db.flush()
            db.add(CardProfile(product_id=row['cardId'], user_id=uid, provider_ref=row['cardId'],
                               expiry_month=12, expiry_year=stamp.year+3, settlement_product_id=row['accountId']))
            for bill in row['bills']:
                db.add(PhoneBill(id=bill['id'], user_id=uid, service_id=bill['serviceId'], reference=bill['reference'],
                                 period=bill['period'], due_date=bill['dueDate'], amount_minor=bill['amountMinor'],
                                 allow_partial=bill['allowPartial'], currency='MXN'))
            for tx in row['transactions']:
                db.add(Transaction(id=tx['id'], user_id=uid, product_id=tx['productId'], merchant=tx['merchant'],
                                   category=tx['category'], amount_minor=tx['amountMinor'], status=tx['status'],
                                   occurred_at=tx['date'], currency='MXN'))
            db.flush()
            if case['id'] == 'pendiente':
                bill = row['bills'][0]; tx = row['transactions'][-1]; ident = 'UX-PAY-'+manifest['runId']
                receipt = {'id': ident, 'billId': bill['id'], 'transactionId': tx['id'], 'serviceId': 'phone-bill',
                           'provider': case['merchant'], 'reference': bill['reference'], 'period': bill['period'],
                           'amountMinor': bill['amountMinor'], 'billAmountMinor': bill['amountMinor'], 'remainingMinor': 0,
                           'currency': 'MXN', 'accountLast4': row['accountLast4'], 'date': tx['date'].isoformat(), 'status': 'pending'}
                db.add(BillPayment(id=ident, user_id=uid, bill_id=bill['id'], account_id=row['accountId'], transaction_id=tx['id'],
                                   request_key='ux-pending-'+manifest['runId'], receipt=receipt, created_at=tx['date']))
                db.add(AuditEvent(id='ux-pending-'+manifest['runId'], user_id=uid, actor_id=uid, action='phone_bill_pending',
                                  transaction_id=tx['id'], product_id=row['accountId'], created_at=tx['date']))
            db.add(AuditEvent(id='ux-created-'+manifest['runId']+'-'+case['id'], user_id=uid, actor_id=uid,
                              action='ux_fixture_created', created_at=stamp))
        db.flush()
    if other_records_hash(db, owners) != before: raise ValueError('Existing records changed; abort the UX insertion')
    users = [{key: value for key, value in row.items() if key not in ('transactions', 'createdAt')}
             | {'balanceMinor': db.get(Product, row['accountId']).balance_minor,
                'requestCount': len(db.scalars(select(RequestCase).where(RequestCase.user_id == row['userId'])).all())}
             for row in plan]
    return {'schemaVersion': 1, 'packId': manifest['packId'], 'runId': manifest['runId'], 'created': not bool(existing),
            'otherRecordsPreserved': True, 'users': users}


def main():
    from .db import make_engine, make_sessions
    url = make_url(os.environ.get('DATABASE_URL', ''))
    if (os.environ.get('NEXQORI_LOCAL_VERIFY') != '1' or url.host != 'db'
            or url.database != 'nexqori' or url.get_backend_name() != 'postgresql'):
        raise RuntimeError('Only explicit local Nexqori Compose is supported')
    manifest = json.loads(sys.stdin.buffer.read(32769))
    engine = make_engine()
    try:
        with make_sessions(engine)() as db:
            with db.begin(): result = ensure_pack(db, manifest)
        print(json.dumps(result, ensure_ascii=False))
    finally: engine.dispose()


if __name__ == '__main__':
    try: main()
    except Exception as error:
        # SQL diagnostics may include a password hash or owner. Keep stderr safe.
        print(json.dumps({'error': type(error).__name__, 'message': 'UX package was not applied. Check local configuration and package consistency.'}), file=sys.stderr)
        raise SystemExit(1)
