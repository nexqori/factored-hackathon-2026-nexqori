"""Deterministic history, deployment adoption, atomic conflicts and safe repeats."""
import pytest
from sqlalchemy import text
from backend.tests.test_api import setup
from backend.db import make_sessions
from backend.models import User, Product, Transaction, AuditEvent
from backend.six_month_demo import demo_plan, ensure_demo, audit_demo, validate_manifest
from backend.ux_fixtures import other_records_hash


def manifest():
    return dict(schemaVersion=1, profileId='verify-six-month-test', name='Sample Owner',
                email='six-month@example.com', document='SIX-001-TEST', password='Test-only-six-month-2026!')


def test_plan_meets_each_month_and_merchant_requirement():
    plan = demo_plan(manifest())
    assert plan == demo_plan(manifest())
    assert len(plan['rows']) == 241
    assert plan['balances'] == {'account':15455004, 'savings':2400000, 'credit':0}
    assert all(r['availableAfterExpensesAndSavingsMinor'] > r['incomeMinor']/2 for r in plan['monthly'])
    for month in range(4,10):
        rows = [r for r in plan['rows'] if r['occurred_at'].month == month]
        assert len(rows) <= 50
        assert sum(r['merchant']=='Ingreso mensual' and r['amount_minor']==4000000 for r in rows)==1
        assert sum(r['product_id']==plan['ids']['savings'] and r['amount_minor']==400000 for r in rows)==1
        for kind in ('credit','debit'):
            assert sum(r['merchant'].startswith('App Taxi') and r['product_id']==plan['ids'][kind] for r in rows)==10
        assert sum(r['merchant'].startswith('Restaurante ') for r in rows)==10
        assert sum('Fibra Aurora' in r['merchant'] for r in rows)==1
        assert sum('Energia Luminara' in r['merchant'] for r in rows)==1
        assert sum(r['merchant'].startswith('Mantenimiento edificio') and r['product_id']==plan['ids']['debit'] for r in rows)==1
        assert sum(r['amount_minor'] for r in rows if r['product_id']==plan['ids']['credit'])==0
    flights=[r for r in plan['rows'] if r['merchant'].startswith('Vuelo nacional')]
    assert len(flights)==1 and flights[0]['amount_minor']==-380000
    assert all(abs(r['amount_minor'])<380000 for r in plan['rows'] if r['merchant'].startswith('App Taxi'))
    assert not any('prueba' in r['merchant'] for r in plan['rows'])
    assert {r['merchant'].split(' - ')[0] for r in plan['rows'] if r['merchant'].startswith('Restaurante ')} == {
        'Restaurante La Terraza del Sol','Restaurante Casa del Maiz','Restaurante El Patio Verde','Restaurante Brasa y Canela'}
    assert all(r['merchant'].endswith(r['occurred_at'].strftime('%Y%m%d')+'1200') for r in plan['rows'] if r['merchant'].startswith(('Restaurante','App Taxi','Internet','Electricidad')))


def test_creation_audit_and_repeat_preserve_other_owners_and_later_activity(setup):
    _,engine=setup;cfg=manifest()
    with make_sessions(engine)() as db:
        before=other_records_hash(db,[cfg['profileId']])
        with db.begin_nested():
            assert ensure_demo(db,cfg)['created']
        db.commit()
        assert audit_demo(db,cfg)['verified']
        assert other_records_hash(db,[cfg['profileId']])==before
        db.get(User,cfg['profileId']).name='Later profile edit'
        db.get(Product,cfg['profileId']+'-account').balance_minor+=10000
        db.add(Transaction(id='later-demo-income',user_id=cfg['profileId'],product_id=cfg['profileId']+'-account',merchant='Later income',category='income',amount_minor=10000,currency='MXN',occurred_at=demo_plan(cfg)['rows'][-1]['occurred_at'],status='completed'))
        db.commit()
        assert not ensure_demo(db,cfg)['created'];db.commit()
        assert db.get(User,cfg['profileId']).name=='Later profile edit'
        assert db.get(Product,cfg['profileId']+'-account').balance_minor==15465004
        assert db.get(Transaction,'later-demo-income') is not None
        assert other_records_hash(db,[cfg['profileId']])==before


def test_adopts_already_created_local_fixture_without_duplicate_or_reset(setup):
    _,engine=setup;cfg=manifest()
    with make_sessions(engine)() as db:
        with db.begin(): ensure_demo(db,cfg)
        assert audit_demo(db,cfg)['verified']
        before=other_records_hash(db,[])
        assert not ensure_demo(db,cfg)['created'];db.commit()
        assert other_records_hash(db,[])==before


def test_failure_rolls_back_every_new_row(setup):
    _,engine=setup;cfg=manifest()
    with engine.begin() as conn:
        conn.execute(text("CREATE TRIGGER fail_demo BEFORE INSERT ON audit_events WHEN NEW.action='synthetic_fixture_created' BEGIN SELECT RAISE(ABORT, 'controlled'); END"))
    with make_sessions(engine)() as db:
        before=other_records_hash(db,[]);db.rollback()
        with pytest.raises(Exception):
            with db.begin(): ensure_demo(db,cfg)
        assert other_records_hash(db,[])==before


@pytest.mark.parametrize('field,value', [('profileId','andrea'),('email','andrea@nexqori.com'),('document','00000001')])
def test_existing_profile_is_never_overwritten(setup,field,value):
    _,engine=setup;cfg=manifest();cfg[field]=value
    with make_sessions(engine)() as db:
        before=other_records_hash(db,[]);db.rollback()
        with pytest.raises(ValueError):
            with db.begin(): ensure_demo(db,cfg)
        assert other_records_hash(db,[])==before


def test_partial_history_requires_inspection_instead_of_recreation(setup):
    _,engine=setup;cfg=manifest()
    with make_sessions(engine)() as db:
        with db.begin(): ensure_demo(db,cfg)
        db.delete(db.get(Transaction,cfg['profileId']+'-tx-0001'));db.commit()
        with pytest.raises(ValueError): ensure_demo(db,cfg)
        assert db.get(Transaction,cfg['profileId']+'-tx-0001') is None


def test_manifest_normalizes_document_without_default_credentials():
    assert validate_manifest(manifest())['document']=='SIX001TEST'
    with pytest.raises(ValueError): validate_manifest({})
