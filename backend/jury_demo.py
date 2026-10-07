"""Explicit public evaluation accounts. Passwords are intentionally public demo values."""
import json
import sys
from sqlalchemy import select
from backend.models import User, Transaction, BillPayment, AuditEvent
from backend.security import hasher, verify
from backend.ux_fixtures import CASES, manifest_plan, ensure_profiles, other_records_hash
from backend.spending_scenarios import ensure_spending_cases

CUSTOMER_PASSWORD = 'Nexqori-Jurado-Cliente-2026!'  # Public demo access, not an infrastructure secret.
ADMIN_PASSWORD = 'Nexqori-Jurado-Admin-2026!'  # Public demo access, not an infrastructure secret.
ADMIN_ID = 'jury-demo-admin'


def prepare(db):
    manifest = {'schemaVersion': 1, 'packId': 'jury-demo', 'runId': '20261006cafe',
                'createdAt': '2026-10-06T18:00:00+00:00',
                'passwords': {case['id']: CUSTOMER_PASSWORD for case in CASES}}
    person = manifest_plan(manifest)[0]
    person.update(email='cliente.demo@nexqori.com', identityNumber='JURADOCLIENTE')
    person['case'] = dict(person['case'], name='Alex Torres')
    before = other_records_hash(db, [person['userId'], ADMIN_ID])
    result = ensure_profiles(db, manifest, [person])
    customer = db.get(User, person['userId'])
    assert customer.email == person['email'] and customer.role == 'customer'
    assert verify(CUSTOMER_PASSWORD, customer.password_hash), 'Existing demo password differs; preserve it'
    scenario = ensure_spending_cases(db, person)
    if result['created']:
        customer.locale = 'en'
    if scenario['created']:
        # The fixture already debited this amount while pending. Post it once,
        # without a second debit, so the administrator can refund the charge.
        charge = db.get(Transaction, scenario['transactionIds'][1])
        assert charge.status == 'pending' and charge.amount_minor == -45900
        charge.status = 'completed'
        payment = db.scalar(select(BillPayment).where(BillPayment.transaction_id == charge.id))
        assert payment and payment.user_id == customer.id
        payment.receipt = {**payment.receipt, 'status': 'completed'}
    admin = db.get(User, ADMIN_ID)
    if admin:
        assert admin.email == 'admin.demo@nexqori.com' and admin.role == 'admin'
        assert verify(ADMIN_PASSWORD, admin.password_hash), 'Existing demo password differs; preserve it'
    else:
        admin = User(id=ADMIN_ID, name='Administracion Demo', email='admin.demo@nexqori.com',
                     identity_number='JURADOADMIN', role='admin', locale='en', password_hash=hasher.hash(ADMIN_PASSWORD))
        db.add(admin); db.flush()
        db.add(AuditEvent(id='jury-demo-admin-created', user_id=admin.id, actor_id=admin.id, action='ux_fixture_created'))
    db.flush()
    assert other_records_hash(db, [person['userId'], ADMIN_ID]) == before, 'Existing customer data changed'
    return {'customerId': customer.id, 'customerEmail': customer.email, 'adminEmail': admin.email,
            'phoneTransactionId': scenario['transactionIds'][1], 'marketTransactionId': scenario['transactionIds'][0],
            'created': result['created'], 'otherRecordsPreserved': True}


def main():
    if sys.argv[1:] != ['--confirm-public-demo']:
        raise SystemExit('Use --confirm-public-demo only on a synthetic demo database.')
    from backend.db import make_engine, make_sessions
    with make_sessions(make_engine())() as db:
        with db.begin():
            result = prepare(db)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
