"""Only isolated SQLite fixtures; never edits the manual demo profile."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from backend.bryan_demo import demo_plan, ensure_demo
from backend.db import make_sessions
from backend.models import (AuditEvent, Conversation, NotificationPreference, Product,
                            RequestCase, ServiceAgreement, Transaction, User)
from backend.tests.test_api import ORIGIN, login, setup
from backend.ux_fixtures import other_records_hash


def manifest():
    return {'schemaVersion': 1, 'runId': uuid4().hex[:12],
            'createdAt': '2026-10-04T15:00:00Z', 'password': uuid4().hex}


def test_one_independent_bryan_can_read_mxn_history_and_conditions(setup):
    app, engine = setup
    pack = manifest()
    with make_sessions(engine)() as db:
        count = db.scalar(select(func.count()).select_from(User))
        before = other_records_hash(db, [])
        db.commit()
        with db.begin():
            result = ensure_demo(db, pack)
        user = result['users'][0]
        uid = user['userId']
        assert db.scalar(select(func.count()).select_from(User)) == count + 1
        assert db.get(User, uid).name == 'Bryan'
        assert other_records_hash(db, [uid]) == before
        assert result['currency'] == 'MXN' and result['created']
        txs = db.scalars(select(Transaction).where(Transaction.user_id == uid)).all()
        assert len(txs) == 18 and {tx.currency for tx in txs} == {'MXN'}
        assert user['balanceMinor'] == 258700
        terms = db.scalar(select(ServiceAgreement).where(ServiceAgreement.user_id == uid))
        assert terms.monthly_minor == 29900 and terms.currency == 'MXN'
        for model in (RequestCase, Conversation, NotificationPreference):
            assert not db.scalar(select(model).where(model.user_id == uid))
    with TestClient(app) as client:
        signed = client.post('/api/auth/login', headers={'Origin': ORIGIN},
                             json={'identifier': user['email'], 'password': pack['password']})
        assert signed.status_code == 200
        boot = client.get('/api/bootstrap').json()
        assert len(boot['transactions']) == 18 and boot['requests'] == []
        phone_id = result['scenario']['transactionIds'][1]
        comparison = client.get('/api/movements/'+phone_id+'/trend').json()['comparison']
        assert comparison['averageMinor'] == 29900 and comparison['count'] == 5
        assert comparison['unusualIncrease']
        other, _ = login(app, 'mateo')
        assert other.get('/api/movements/'+phone_id+'/trend').status_code == 404


def test_repeat_preserves_new_activity_and_does_not_add_rows(setup):
    _, engine = setup
    pack = manifest()
    with make_sessions(engine)() as db:
        with db.begin():
            first = ensure_demo(db, pack)
        user = first['users'][0]
        db.get(User, user['userId']).email = 'bryan-test@example.com'
        db.get(Product, user['accountId']).balance_minor -= 100
        db.add(RequestCase(id='BRYAN-AFTER-CREATION', user_id=user['userId'], request_key=str(uuid4()),
                           service='support', reason='other', details='Keep the later case.'))
        db.commit()
        before = other_records_hash(db, [])
        audits = db.scalar(select(func.count()).select_from(AuditEvent))
        db.commit()
        with db.begin():
            repeated = ensure_demo(db, pack)
        assert not repeated['created'] and not repeated['scenario']['created']
        assert repeated['users'][0]['requestCount'] == 1
        assert repeated['users'][0]['email'] == 'bryan-test@example.com'
        assert repeated['users'][0]['balanceMinor'] == user['balanceMinor'] - 100
        assert other_records_hash(db, []) == before
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == audits


def test_failure_while_building_history_rolls_back_the_whole_new_profile(setup):
    _, engine = setup
    with engine.begin() as conn:
        conn.execute(text("CREATE TRIGGER reject_spending BEFORE INSERT ON audit_events "
                          "WHEN NEW.action = 'spending_fixture_created' "
                          "BEGIN SELECT RAISE(ABORT, 'controlled failure'); END"))
    with make_sessions(engine)() as db:
        before = other_records_hash(db, [])
        db.commit()
        with pytest.raises(Exception):
            with db.begin():
                ensure_demo(db, manifest())
        assert other_records_hash(db, []) == before


def test_never_renames_an_existing_profile_with_the_same_identifier(setup):
    _, engine = setup
    pack = manifest()
    _, person = demo_plan(pack)
    with make_sessions(engine)() as db:
        db.add(User(id=person['userId'], name='Camila', email='untouched@nexqori.com',
                    password_hash='untouched', role='customer'))
        db.commit()
        before = other_records_hash(db, [])
        db.commit()
        with pytest.raises(ValueError, match='another profile'):
            with db.begin():
                ensure_demo(db, pack)
        assert other_records_hash(db, []) == before
