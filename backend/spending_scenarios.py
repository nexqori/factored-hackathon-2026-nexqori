"""Opt-in constructed spending history, not customer data from the source dataset.

No reset API is shipped. Creation uses the existing private UX package manifest.
"""
import json
import os
import sys
from datetime import timedelta
from sqlalchemy import select
from sqlalchemy.engine import make_url
from .models import AuditEvent, BillPayment, CardProfile, PhoneBill, Product, Transaction, User, ServiceAgreement
from .ux_fixtures import manifest_plan


def scenario_plan(person):
    suffix = person['userId'].removeprefix('ux-user-')
    stamp = person['createdAt']
    uid = person['userId']
    # A separate line avoids changing bills the customer may already have paid.
    reference = '55' + str((int(person['bills'][0]['reference'][2:]) + 7) % 10**8).zfill(8)
    rows = []
    for kind, merchant, product, category, amounts in [
        ('shop', 'Mercado del Barrio', person['cardId'], 'shopping', [60000,61000,59000,62000,58000]),
        ('phone', 'Empresa Telefónica', person['accountId'], 'utilities', [29900]*5),
    ]:
        for index, amount in enumerate(amounts + ([270000] if kind == 'shop' else [45900])):
            month = stamp.year*12 + stamp.month-1 - (5-index)
            date = stamp.replace(year=month//12,month=month%12+1,day=min(stamp.day,28)) if index < 5 else stamp - timedelta(minutes=40 if kind == 'shop' else 20)
            rows.append({'id':f'TREND-{kind}-{index}-{suffix}', 'userId':uid, 'productId':product,
                'merchant':merchant, 'category':category, 'amountMinor':-amount,
                'status':'pending' if kind=='phone' and index==5 else 'completed', 'date':date,
                'billId':f'trend-bill-{index}-{suffix}' if kind=='phone' else None,
                'paymentId':f'TREND-PAY-{index}-{suffix}' if kind=='phone' else None})
    return {'userId':uid, 'marker':'trends-created-'+suffix, 'reference':reference, 'rows':rows,
            'transactionIds':[r['id'] for r in rows if '-5-' in r['id']],
            'fundingId':'TREND-FUND-'+suffix, 'fundingMinor':700000}


def ensure_example_agreement(db,plan):
    first=min(r['date'] for r in plan['rows']).date().replace(day=1)
    last=first.replace(year=first.year+1)-timedelta(days=1)
    terms={'id':'terms-'+plan['userId'],'user_id':plan['userId'],'service_id':'phone-bill',
           'reference':plan['reference'],'provider_id':'empresa-telefonica','plan_id':'telefono-esencial',
           'plan_name':'Teléfono Esencial','version':1,'valid_from':first,'valid_until':last,
           'monthly_minor':29900,'currency':'MXN','taxes_included':True,
           'extras_require_approval':True,'source':'constructed_fixture'}
    existing=db.get(ServiceAgreement,terms['id'])
    if existing:
        if any(getattr(existing,k)!=v for k,v in terms.items()):
            raise ValueError('Existing service conditions differ; do not overwrite')
        return
    db.add(ServiceAgreement(**terms))
    db.add(AuditEvent(id='terms-created-'+plan['userId'],user_id=plan['userId'],actor_id=plan['userId'],action='service_conditions_created'))
    db.flush()


def ensure_spending_cases(db, person):
    if person['case']['id'] != 'cargo':
        raise ValueError('The spending scenarios belong to the cargo UX profile')
    plan = scenario_plan(person); uid = plan['userId']
    owner = db.scalar(select(User).where(User.id == uid).with_for_update())
    original = db.get(AuditEvent, 'ux-created-'+uid.removeprefix('ux-user-'))
    account = db.scalar(select(Product).where(Product.id == person['accountId'], Product.user_id == uid).with_for_update())
    card = db.get(CardProfile, person['cardId'])
    if not owner or not original or original.user_id!=uid or not account or not card or card.user_id!=uid or card.settlement_product_id!=account.id:
        raise ValueError('Verified UX owner and settlement account required')
    marker = db.get(AuditEvent, plan['marker'])
    if marker:
        if marker.user_id != uid or marker.action != 'spending_fixture_created':
            raise ValueError('Invalid scenario marker')
        for row in plan['rows']:
            tx = db.get(Transaction, row['id'])
            if not tx or tx.user_id != uid: raise ValueError('Incomplete scenarios; do not overwrite')
        ensure_example_agreement(db,plan)
        return {k:v for k,v in plan.items() if k!='rows'} | {'created':False}
    # Every insertion and the ledger change must commit together.
    db.add(Transaction(id=plan['fundingId'],user_id=uid,product_id=account.id,merchant='Ingreso de ahorro',
        category='income',amount_minor=plan['fundingMinor'],currency='MXN',status='completed',
        occurred_at=min(row['date'] for row in plan['rows'])-timedelta(days=1)))
    for row in plan['rows']:
        db.add(Transaction(id=row['id'],user_id=uid,product_id=row['productId'],merchant=row['merchant'],
            category=row['category'],amount_minor=row['amountMinor'],currency='MXN',status=row['status'],occurred_at=row['date']))
    db.flush()
    for row in plan['rows']:
        if not row['billId']: continue
        period = row['date'].strftime('%Y-%m')
        bill = PhoneBill(id=row['billId'],user_id=uid,service_id='phone-bill',reference=plan['reference'],
            period=period,due_date=period+'-20',amount_minor=-row['amountMinor'],currency='MXN')
        db.add(bill); db.flush()
        receipt = {'id':row['paymentId'],'billId':bill.id,'transactionId':row['id'],'serviceId':'phone-bill',
            'providerId':'empresa-telefonica','planId':'telefono-esencial',
            'provider':row['merchant'],'reference':plan['reference'],'period':period,'amountMinor':bill.amount_minor,
            'billAmountMinor':bill.amount_minor,'remainingMinor':0,'currency':'MXN','accountLast4':account.last4,
            'date':row['date'].isoformat(),'status':row['status']}
        db.add(BillPayment(id=row['paymentId'],user_id=uid,bill_id=bill.id,account_id=account.id,transaction_id=row['id'],
            request_key=row['paymentId'],receipt=receipt,created_at=row['date']))
        db.add(AuditEvent(id='event-'+row['paymentId'],user_id=uid,actor_id=uid,product_id=account.id,
            transaction_id=row['id'],action='phone_bill_pending' if row['status']=='pending' else 'phone_bill_paid',created_at=row['date']))
    account.balance_minor += plan['fundingMinor'] + sum(r['amountMinor'] for r in plan['rows'])
    if account.balance_minor < 0: raise ValueError('Scenario cannot overdraw the account')
    db.add(AuditEvent(id=plan['marker'],user_id=uid,actor_id=uid,action='spending_fixture_created'))
    ensure_example_agreement(db,plan)
    db.flush()
    return {k:v for k,v in plan.items() if k!='rows'} | {'created':True}


def main():
    from .db import make_engine, make_sessions
    url = make_url(os.environ.get('DATABASE_URL', ''))
    if os.environ.get('NEXQORI_LOCAL_VERIFY')!='1' or url.host!='db' or url.database!='nexqori' or url.get_backend_name()!='postgresql':
        raise ValueError('Only explicit local Compose supported')
    manifest=json.loads(sys.stdin.buffer.read(32769)); person=manifest_plan(manifest)[0]
    engine=make_engine()
    try:
        with make_sessions(engine)() as db:
            with db.begin(): result=ensure_spending_cases(db,person)
        print(json.dumps(result))
    finally: engine.dispose()


if __name__=='__main__':
    try: main()
    except Exception:
        print('Spending scenarios not applied; check package consistency.',file=sys.stderr)
        raise SystemExit(1)
