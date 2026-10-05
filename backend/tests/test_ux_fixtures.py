"""Fixture creation runs only in isolated SQLite here, never the local bank."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from backend.db import make_sessions
from backend.models import (AuditEvent, BillPayment, CardProfile, Conversation, CustomerProfile,
                            PhoneBill, Product, Refund, RequestCase, Transaction, User)
from backend.security import hasher
from backend.ux_fixtures import CASES, ensure_pack, manifest_plan, other_records_hash
from backend.tests.test_api import ORIGIN, setup


def manifest():
    return {'schemaVersion': 1, 'packId': 'isolated-ux', 'runId': uuid4().hex[:12],
            'createdAt': '2026-10-03T15:00:00Z',
            'passwords': {case['id']: 'Isolated-UX-' + uuid4().hex for case in CASES}}


def test_five_initial_profiles_have_records_and_no_resolved_cases(setup):
    _, engine = setup; pack = manifest()
    with make_sessions(engine)() as db:
        with db.begin(): result = ensure_pack(db, pack)
        assert result['created'] and result['otherRecordsPreserved']
        assert len(result['users']) == 5
        last4s = [db.get(Product, person[key]).last4 for person in result['users']
                  for key in ('accountId', 'savingsId', 'cardId')]
        assert len(set(last4s)) == 15
        for person in result['users']:
            owner = person['userId']; user = db.get(User, owner)
            assert user.role == 'customer' and hasher.verify(user.password_hash, pack['passwords'][person['case']['id']])
            assert db.get(CustomerProfile, owner) is not None
            assert db.get(CardProfile, person['cardId']).status == 'active'
            assert db.get(Product, person['accountId']).balance_minor == person['balanceMinor']
            assert db.scalar(select(func.count()).select_from(Transaction).where(Transaction.user_id == owner)) == 5
            assert db.scalar(select(func.count()).select_from(PhoneBill).where(PhoneBill.user_id == owner)) == 4
            for model in (Conversation, RequestCase, Refund):
                assert db.scalar(select(func.count()).select_from(model).where(model.user_id == owner)) == 0
            assert person['requestCount'] == 0
            primary = db.get(Transaction, person['transactionId'])
            assert primary.status == person['case']['status'] and primary.amount_minor == -person['case']['amountMinor']
            assert person['previousMonth'] == {'startDate': '2026-09-01', 'endDate': '2026-09-30'}
            if person['case']['id'] == 'pendiente':
                payment = db.scalar(select(BillPayment).where(BillPayment.user_id == owner))
                assert payment.receipt['status'] == 'pending' and payment.transaction_id == primary.id
                assert payment.receipt['amountMinor'] == 29900
                assert payment.receipt['accountLast4'] == person['accountLast4']
            else:
                assert not db.scalar(select(BillPayment).where(BillPayment.user_id == owner))


def test_same_manifest_is_idempotent_and_does_not_reset_later_user_activity(setup):
    _, engine = setup; pack = manifest()
    with make_sessions(engine)() as db:
        with db.begin(): first = ensure_pack(db, pack)
        person = first['users'][0]
        db.get(Product, person['accountId']).balance_minor -= 100
        db.add(RequestCase(id='UX-REQUEST-AFTER-CREATION', user_id=person['userId'], request_key=str(uuid4()),
                           service='support', reason='other', details='A later request must remain intact.'))
        db.get(CardProfile, person['cardId']).status = 'blocked'
        db.commit()
        before = other_records_hash(db, [])
        count = db.scalar(select(func.count()).select_from(AuditEvent)); db.commit()
        with db.begin(): second = ensure_pack(db, pack)
        assert not second['created'] and second['users'][0]['requestCount'] == 1
        assert second['users'][0]['balanceMinor'] == first['users'][0]['balanceMinor'] - 100
        assert db.get(CardProfile, person['cardId']).status == 'blocked'
        assert other_records_hash(db, []) == before
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == count


@pytest.mark.parametrize('identifier_field', ['email', 'identityNumber'])
def test_profiles_can_sign_in_and_read_owned_records_without_repaying_pending_bill(setup, identifier_field):
    app, engine = setup; pack = manifest()
    with make_sessions(engine)() as db:
        with db.begin(): result = ensure_pack(db, pack)
    for person in result['users']:
        with TestClient(app) as client:
            logged = client.post('/api/auth/login', headers={'Origin': ORIGIN},
                                 json={'identifier': person[identifier_field], 'password': pack['passwords'][person['case']['id']]})
            assert logged.status_code == 200
            client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': logged.json()['csrfToken']})
            before = client.get('/api/bootstrap').json()
            assert {p['id'] for p in before['products']} == {person['accountId'], person['savingsId'], person['cardId']}
            assert len(before['transactions']) == 5 and before['requests'] == []
            assert client.get('/api/cards').json()['cards'][0]['last4'] == person['last4']
            assert len(client.get('/api/service-bills/references').json()['references']) == 4
            phone = next(b for b in client.get('/api/phone-bills').json()['bills'] if b['id'] == person['bills'][0]['id'])
            if person['case']['id'] == 'pendiente':
                assert phone['paymentStatus'] == 'pending' and phone['pendingMinor'] == 29900
                assert phone['outstandingMinor'] == 0 and phone['paidMinor'] == 0
                receipt = client.get('/api/payments/'+phone['pendingPaymentId']).json()
                assert receipt['transactionId'] == person['transactionId'] and receipt['status'] == 'pending'
                retried = client.post('/api/service-bills/'+phone['id']+'/pay', json={
                    'confirmed': True, 'accountId': person['accountId'], 'requestKey': str(uuid4()),
                    'mode': 'total', 'expectedOutstandingMinor': 29900})
                assert retried.status_code == 409 and retried.json()['error'] == 'bill_in_processing'
            else:
                assert phone['paymentStatus'] == 'unpaid' and phone['outstandingMinor'] == 29900
            assert client.get('/api/bootstrap').json() == before
            assert client.post('/api/auth/logout', json={}).status_code == 200


def test_fixture_insertion_is_atomic_when_any_marker_cannot_be_saved(setup):
    _, engine = setup; pack = manifest()
    with engine.begin() as connection:
        connection.execute(text("CREATE TRIGGER reject_ux BEFORE INSERT ON audit_events "
                                "WHEN NEW.action = 'ux_fixture_created' BEGIN SELECT RAISE(ABORT, 'controlled UX failure'); END"))
    with make_sessions(engine)() as db:
        before = other_records_hash(db, []); db.commit()
        with pytest.raises(Exception):
            with db.begin(): ensure_pack(db, pack)
        assert other_records_hash(db, []) == before
        assert not db.scalar(select(User).where(User.id.like('ux-user-%')))


def test_incomplete_or_foreign_package_is_never_repaired_or_overwritten(setup):
    _, engine = setup; pack = manifest(); planned = manifest_plan(pack)
    with make_sessions(engine)() as db:
        person = planned[0]
        db.add(User(id=person['userId'], name='Existing record', email='occupied@nexqori.com',
                    role='customer', password_hash='not-a-fixture-password'))
        db.commit(); before = other_records_hash(db, []); db.commit()
        with pytest.raises(ValueError, match='Incomplete UX package'):
            with db.begin(): ensure_pack(db, pack)
        assert other_records_hash(db, []) == before


@pytest.mark.parametrize('change', ['owner', 'path', 'run', 'short-password', 'missing-case'])
def test_manifest_cannot_select_existing_owner_or_smuggle_configuration(setup, change):
    _, engine = setup; pack = manifest()
    if change == 'owner': pack['userId'] = 'andrea'
    elif change == 'path': pack['packId'] = '../../outside'
    elif change == 'run': pack['runId'] = 'andrea'
    elif change == 'short-password': pack['passwords']['cargo'] = 'short'
    else: pack['passwords'].pop('cargo')
    with make_sessions(engine)() as db:
        before = other_records_hash(db, []); db.commit()
        with pytest.raises(ValueError):
            with db.begin(): ensure_pack(db, pack)
        assert other_records_hash(db, []) == before


def test_month_boundaries_and_catalog_provenance_are_stable():
    from backend.catalog import SERVICES
    pack = manifest(); pack['createdAt'] = '2027-01-01T05:30:00Z'  # Still December in Mexico City.
    plan = manifest_plan(pack)
    assert all(row['previousMonth'] == {'startDate': '2026-11-01', 'endDate': '2026-11-30'} for row in plan)
    providers = {item['provider'] for item in SERVICES.values() if item['kind'] == 'bill'}
    assert all(case['merchant'] in providers for case in CASES)
    assert all(set(case['messages']) == {'es', 'en', 'pt'} for case in CASES)
    assert all(case['intent'] in SERVICES for case in CASES)


def test_team_alias_upgrade_preserves_activity_and_custom_email(setup):
    from backend.demo_emails import UX_EMAILS
    _, engine = setup; pack = manifest()
    with make_sessions(engine)() as db:
        with db.begin(): old = ensure_pack(db, pack)
        people = old['users']
        original_hashes = {p['userId']: db.get(User, p['userId']).password_hash for p in people}
        db.get(User, people[-1]['userId']).email = 'custom@example.test'
        db.get(Product, people[0]['accountId']).balance_minor -= 123
        db.add(RequestCase(id='alias-existing-claim', user_id=people[0]['userId'], request_key=str(uuid4()),
                           service='support', reason='other', details='Preserve this claim.'))
        db.commit()
        outside = other_records_hash(db, [p['userId'] for p in people]); db.commit()
        pack['packId'] = 'equipo-ux'
        with db.begin(): upgraded = ensure_pack(db, pack)
        assert not upgraded['created']
        for p in upgraded['users']:
            expected = 'custom@example.test' if p['case']['id'] == 'documentos' else UX_EMAILS[p['case']['id']]
            assert p['email'] == db.get(User, p['userId']).email == expected
            assert db.get(User, p['userId']).password_hash == original_hashes[p['userId']]
        assert upgraded['users'][0]['balanceMinor'] == people[0]['balanceMinor'] - 123
        assert upgraded['users'][0]['requestCount'] == 1
        assert other_records_hash(db, [p['userId'] for p in people]) == outside
        before = other_records_hash(db, [])
        audits = db.scalar(select(func.count()).select_from(AuditEvent)); db.commit()
        with db.begin(): ensure_pack(db, pack)
        assert other_records_hash(db, []) == before
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == audits


def test_alias_collision_rolls_back_all_previous_alias_changes(setup):
    from backend.demo_emails import UX_EMAILS
    _, engine = setup; pack = manifest()
    with make_sessions(engine)() as db:
        with db.begin(): ensure_pack(db, pack)
        db.get(User, 'andrea').email = UX_EMAILS['importe']
        db.commit(); before = other_records_hash(db, []); db.commit()
        pack['packId'] = 'equipo-ux'
        with pytest.raises(ValueError, match='already belongs'):
            with db.begin(): ensure_pack(db, pack)
        assert other_records_hash(db, []) == before


def test_new_team_uses_readable_aliases_but_other_packs_remain_unique(setup):
    from backend.demo_emails import UX_EMAILS
    _, engine = setup; pack = manifest(); pack['packId'] = 'equipo-ux'
    with make_sessions(engine)() as db:
        with db.begin(): result = ensure_pack(db, pack)
        assert {p['email'] for p in result['users']} == set(UX_EMAILS.values())
    independent = manifest_plan(manifest())
    assert all(p['email'].startswith('ux-') for p in independent)


def test_base_aliases_preserve_personal_contacts_and_passwords(setup):
    from backend.demo_emails import update_base_demo_emails
    _, engine = setup
    with make_sessions(engine)() as db:
        passwords = {u.id: u.password_hash for u in db.scalars(select(User))}
        db.get(User, 'mateo').email = 'personal@example.test'
        db.add(User(id='bryan', name='Bryan', email='bryan@example.test', role='customer', password_hash='unchanged'))
        db.commit()
        with db.begin(): update_base_demo_emails(db)
        assert db.get(User, 'andrea').email == 'andrea.rivera@nexqori.com'
        assert db.get(User, 'nora').email == 'nora.admin@nexqori.com'
        assert db.get(User, 'mateo').email == 'personal@example.test'
        assert db.get(User, 'bryan').email == 'bryan@example.test'
        assert all(db.get(User, uid).password_hash == value for uid, value in passwords.items())
