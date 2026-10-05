"""Opt-in synthetic six-month profile; private identity and password are never defaults.

The same deterministic history is usable locally and in the public demo. Repeated
startup preserves subsequent customer activity, credentials, balances and names.
"""
import json
import hashlib
import os
import random
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from sqlalchemy import select, or_, text
from sqlalchemy.engine import make_url
from .models import User, Product, CardProfile, Transaction, AuditEvent
from .security import hasher, verify


def renamed_merchant(name, occurred_at):
    restaurants={'1':'La Terraza del Sol','2':'Casa del Maiz','3':'El Patio Verde','4':'Brasa y Canela'}
    name=re.sub(r'Restaurante ([1-4])\b',lambda m:'Restaurante '+restaurants[m[1]],name)
    name=name.replace('Internet mensual - proveedor de prueba','Internet mensual - Fibra Aurora de prueba')
    name=name.replace('Electricidad mensual - proveedor de prueba','Electricidad mensual - Energia Luminara de prueba')
    stamp=(occurred_at if occurred_at.tzinfo else occurred_at.replace(tzinfo=timezone.utc)).astimezone(ZoneInfo('America/Mexico_City')).strftime('%Y%m%d%H%M')
    name=name.replace('de prueba',stamp)
    name=re.sub(r'\bprueba\b',stamp,name)
    return name


def validate_manifest(value):
    keys = {'schemaVersion', 'profileId', 'name', 'email', 'document', 'password'}
    if not isinstance(value, dict) or set(value) != keys or value['schemaVersion'] != 1:
        raise ValueError('Invalid private demo manifest')
    if any(not isinstance(value[k], str) for k in keys - {'schemaVersion'}):
        raise ValueError('Invalid private demo fields')
    cfg = dict(value)
    cfg['email'] = cfg['email'].strip().lower()
    cfg['document'] = cfg['document'].upper().replace('-', '').replace(' ', '')
    if (not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,39}', cfg['profileId'])
            or not 1 <= len(cfg['name'].strip()) <= 100
            or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', cfg['email'])
            or len(cfg['email']) > 254 or not re.fullmatch(r'[A-Z0-9]{3,32}', cfg['document'])
            or not 14 <= len(cfg['password']) <= 128):
        raise ValueError('Invalid private demo values')
    return cfg


def demo_plan(manifest):
    cfg = validate_manifest(manifest)
    uid = cfg['profileId']
    ids={k:uid+'-'+k for k in ('account','savings','credit','debit')}
    rng=random.Random(10052026)
    rows=[]
    def add(month,day,kind,merchant,category,amount):
        rows.append(dict(id=f'{uid}-tx-{len(rows)+1:04}',user_id=uid,product_id=ids[kind],merchant=renamed_merchant(merchant,datetime(2026,month,day,18,tzinfo=timezone.utc)),category=category,amount_minor=amount,currency='MXN',occurred_at=datetime(2026,month,day,18,tzinfo=timezone.utc),status='completed'))
    summaries=[]
    for month in range(4,10):
        start=len(rows); income=4000000
        add(month,1,'account','Ingreso mensual','income',income)
        add(month,2,'account','Transferencia a cuenta de ahorros propia','transfer',-income//10)
        add(month,2,'savings','Ahorro del 10% del ingreso mensual','transfer',income//10)
        add(month,5,'credit','Internet mensual - proveedor de prueba','utilities',-59900)
        add(month,7,'credit','Electricidad mensual - proveedor de prueba','utilities',-rng.randint(45000,85000))
        add(month,8,'debit','Mantenimiento edificio - transferencia a otra cuenta de prueba','transfer',-120000)
        for i in range(10):
            add(month,3+2*i,'credit','App Taxi - viaje de prueba','transport',-rng.randint(8000,22000))
            add(month,4+2*i,'debit','App Taxi - viaje de prueba','transport',-rng.randint(8000,22000))
            add(month,3+2*i,'credit','Restaurante '+str(i%4+1)+' - consumo de prueba','food',-rng.randint(18000,42000))
        if month==7:
            add(month,15,'credit','Vuelo nacional CDMX-Cancun ida y vuelta - prueba','travel',-380000)
        add(month,12,'account','Supermercado - compra de prueba','shopping',-rng.randint(80000,120000))
        add(month,20,'account','Farmacia - compra de prueba','health',-rng.randint(15000,30000))
        credit=-sum(t['amount_minor'] for t in rows[start:] if t['product_id']==ids['credit'])
        add(month,28,'account','Pago total tarjeta de credito 4101','transfer',-credit)
        add(month,28,'credit','Pago recibido desde cuenta de transacciones','transfer',credit)
        monthrows=rows[start:]
        debit=sum(t['amount_minor'] for t in monthrows if t['product_id']==ids['debit'])
        available=sum(t['amount_minor'] for t in monthrows if t['product_id']==ids['account'])+debit
        assert len(monthrows)<=50 and available>income//2
        summaries.append(dict(month=f'2026-{month:02}',records=len(monthrows),incomeMinor=income,savingsMinor=income//10,availableAfterExpensesAndSavingsMinor=available,creditPaidMinor=credit))
    bal=defaultdict(int)
    for t in sorted(rows,key=lambda x:x['occurred_at']):
        kind=next(k for k,v in ids.items() if v==t['product_id'])
        bal['account' if kind=='debit' else kind]+=t['amount_minor']
        assert bal['account']>=0 and bal['savings']>=0
    assert bal['credit']==0
    return {'config': cfg, 'ids': ids, 'rows': rows, 'monthly': summaries, 'balances': dict(bal)}


def ensure_demo(db, manifest):
    """Caller owns the transaction. Collisions fail; repeats never reset activity."""
    plan = demo_plan(manifest)
    cfg, ids = plan['config'], plan['ids']
    uid = cfg['profileId']
    if db.bind.dialect.name == 'postgresql':
        # Serialize initial creation of the same demo across concurrent starts.
        db.execute(text('SELECT pg_advisory_xact_lock(hashtext(:key))'), {'key': 'six-month-demo:' + uid})
    existing = db.get(User, uid)
    if existing:
        marker = db.get(AuditEvent, uid + '-created')
        if not marker or marker.user_id != uid or marker.action != 'synthetic_fixture_created':
            raise ValueError('Existing identity is not this demo')
        for kind, ident in ids.items():
            product = db.get(Product, ident)
            if not product or product.user_id != uid or product.type != (kind if kind in ('account','savings') else 'card'):
                raise ValueError('Incomplete demo products; inspect without resetting')
        for row in plan['rows']:
            tx = db.get(Transaction, row['id'])
            if not tx or tx.user_id != uid or tx.product_id != row['product_id']:
                raise ValueError('Incomplete demo history; inspect without resetting')
        return {'created': False, 'fixtureTransactions': len(plan['rows']), 'existingActivityPreserved': True}
    conflict = db.scalar(select(User.id).where(or_(User.email == cfg['email'], User.identity_number == cfg['document'])))
    if conflict:
        raise ValueError('Email or document belongs to an existing profile')
    db.add(User(id=uid, email=cfg['email'], identity_number=cfg['document'], name=cfg['name'],
                password_hash=hasher.hash(cfg['password']), role='customer', locale='es'))
    db.flush()
    for kind, last4 in [('account','4103'),('savings','4104'),('credit','4101'),('debit','4102')]:
        db.add(Product(id=ids[kind], user_id=uid, type=kind if kind in ('account','savings') else 'card',
                       card_kind=kind if kind in ('credit','debit') else None, last4=last4,
                       balance_minor=plan['balances'][kind] if kind in ('account','savings') else None, currency='MXN'))
    db.flush()
    for kind in ('account', 'savings'):
        db.get(Product, ids[kind]).transfer_reference = '7' + str(int(hashlib.sha256(ids[kind].encode()).hexdigest(),16) % 10**17).zfill(17)
    for kind in ('credit','debit'):
        db.add(CardProfile(product_id=ids[kind], user_id=uid, provider_ref=ids[kind],
                           expiry_month=12, expiry_year=2030, settlement_product_id=ids['account']))
    db.add_all([Transaction(**row) for row in plan['rows']])
    db.add(AuditEvent(id=uid+'-created', user_id=uid, actor_id=uid, action='synthetic_fixture_created'))
    db.flush()
    return {'created': True, 'fixtureTransactions': len(plan['rows']), 'currency': 'MXN', 'monthly': plan['monthly']}


def audit_demo(db, manifest):
    """Strict initial acceptance check; read-only and separate from startup."""
    plan = demo_plan(manifest)
    cfg, ids = plan['config'], plan['ids']
    user = db.get(User, cfg['profileId'])
    if (not user or user.name != cfg['name'] or user.email != cfg['email']
            or user.identity_number != cfg['document'] or not verify(cfg['password'], user.password_hash)):
        raise ValueError('Demo identity or access differs from requested configuration')
    for expected in plan['rows']:
        actual = db.get(Transaction, expected['id'])
        if not actual or any(getattr(actual,k) != expected[k] for k in ('user_id','product_id','merchant','category','amount_minor','currency','status')):
            raise ValueError('Demo movement differs from requested history')
        stamp = actual.occurred_at.replace(tzinfo=timezone.utc) if not actual.occurred_at.tzinfo else actual.occurred_at
        if stamp != expected['occurred_at']:
            raise ValueError('Demo movement timestamp differs')
    for kind, ident in ids.items():
        p = db.get(Product, ident)
        if not p or p.user_id != user.id or p.card_kind != (kind if kind in ('credit','debit') else None):
            raise ValueError('Demo product classification differs')
        if kind in ('account','savings') and p.balance_minor != plan['balances'][kind]:
            raise ValueError('Balance differs from initial demo; inspect subsequent activity')
    return {'verified': True, 'fixtureTransactions': len(plan['rows']), 'monthly': plan['monthly'],
            'initialBalancesMinor': plan['balances'], 'cardKinds': {'4101':'credit','4102':'debit'}}


def main():
    from .db import make_engine, make_sessions
    mode = sys.argv[1:]
    if mode == ['--configured']:
        filename = os.environ.get('NEXQORI_DEMO_PROFILE_FILE')
        path = Path(filename or '/app/demo-config/profile.private.json')
        if not filename and not path.exists():
            return
        with path.open('rb') as source:
            raw = source.read(16385)
    elif mode in (['--apply'], ['--audit']):
        raw = sys.stdin.buffer.read(16385)
    else:
        raise ValueError('Use --configured, --apply or --audit with a private manifest')
    if len(raw) > 16384:
        raise ValueError('Demo manifest too large')
    manifest = json.loads(raw.decode('utf-8-sig'))
    url = make_url(os.environ.get('DATABASE_URL', ''))
    if url.host != 'db' or url.database != 'nexqori' or url.get_backend_name() != 'postgresql':
        raise ValueError('Only the configured Nexqori Compose database is supported')
    engine = make_engine()
    try:
        with make_sessions(engine)() as db:
            with db.begin():
                result = audit_demo(db, manifest) if mode == ['--audit'] else ensure_demo(db, manifest)
        print(json.dumps(result))
    finally:
        engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # DB exceptions may contain credentials or row data: never expose them.
        print('Demo profile not applied/verified; inspect private configuration and existing profile.', file=sys.stderr)
        raise SystemExit(1)
