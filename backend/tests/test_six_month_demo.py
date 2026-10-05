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


def test_sync_updates_only_fixture_identity_labels_and_invalidates_old_access(setup):
    from backend.models import Session, CardProfile
    from backend.security import hasher, verify
    from sqlalchemy import select, func
    _, engine = setup
    cfg = manifest()
    with make_sessions(engine)() as db:
        with db.begin(): ensure_demo(db, cfg)
        user = db.get(User,cfg['profileId'])
        user.name='Old Name';user.email='old-demo@example.com';user.identity_number='OLDTEST'
        user.password_hash=hasher.hash('Another-private-password!')
        db.get(Product,cfg['profileId']+'-credit').card_kind=None
        db.get(CardProfile,cfg['profileId']+'-credit').status='blocked'
        db.get(Product,cfg['profileId']+'-account').balance_minor+=10000
        db.get(Transaction,cfg['profileId']+'-tx-0004').merchant='Old provider'
        db.add(Session(token_hash='a'*64,user_id=user.id,csrf_token='b'*64,expires_at=9999999999))
        db.commit()
        before=other_records_hash(db,[user.id])
        original=[(t.id,t.amount_minor,t.occurred_at,t.status) for t in db.scalars(select(Transaction).where(Transaction.user_id==user.id).order_by(Transaction.id))]
        assert ensure_demo(db,cfg,synchronize=True)['updated'];db.commit()
        assert (user.name,user.email,user.identity_number)==('Sample Owner','six-month@example.com','SIX001TEST')
        assert verify(cfg['password'],user.password_hash)
        assert db.scalar(select(func.count()).select_from(Session).where(Session.user_id==user.id))==0
        assert db.get(Product,user.id+'-credit').card_kind=='credit'
        assert db.get(CardProfile,user.id+'-credit').status=='blocked'
        assert db.get(Product,user.id+'-account').balance_minor==15465004
        assert [(t.id,t.amount_minor,t.occurred_at,t.status) for t in db.scalars(select(Transaction).where(Transaction.user_id==user.id).order_by(Transaction.id))]==original
        assert other_records_hash(db,[user.id])==before
        encoded=user.password_hash
        assert not ensure_demo(db,cfg,synchronize=True)['updated'];db.commit()
        assert user.password_hash==encoded
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action=='demo_profile_synchronized'))==1


def test_sync_conflicting_identity_rolls_back_without_touching_users(setup):
    _,engine=setup;cfg=manifest()
    with make_sessions(engine)() as db:
        with db.begin(): ensure_demo(db,cfg)
        before=other_records_hash(db,[]);db.rollback()
        cfg['email']='andrea@nexqori.com'
        with pytest.raises(ValueError):
            with db.begin(): ensure_demo(db,cfg,synchronize=True)
        assert other_records_hash(db,[])==before


def test_configured_json_precedes_file_and_missing_required_config_fails(tmp_path):
    import json
    from backend.six_month_demo import configured_manifest
    missing=str(tmp_path/'missing.json')
    env={'NEXQORI_DEMO_REQUIRED':'true','NEXQORI_DEMO_PROFILE_FILE':missing}
    with pytest.raises(ValueError): configured_manifest(env)
    cfg=manifest()
    assert configured_manifest({**env,'NEXQORI_DEMO_PROFILE_JSON':json.dumps(cfg)})==validate_manifest(cfg)
    assert configured_manifest({**env,'NEXQORI_DEMO_ENABLED':'false'}) is None
    path=tmp_path/'private.json';path.write_text(json.dumps(cfg),encoding='utf-8')
    assert configured_manifest({**env,'NEXQORI_DEMO_PROFILE_FILE':str(path)})==validate_manifest(cfg)
    with pytest.raises(ValueError): configured_manifest({**env,'NEXQORI_DEMO_PROFILE_JSON':'x'*16385})
    with pytest.raises(ValueError): configured_manifest({**env,'NEXQORI_DEMO_PROFILE_JSON':'invalid'})
    with pytest.raises(ValueError): configured_manifest({'NEXQORI_DEMO_ENABLED':'typo'})
