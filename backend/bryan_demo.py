"""Create Bryan's independent MXN demo from the same synthetic Camila scenario.

No customer rows, conversations, notification addresses or credentials are copied.
Only the explicit local command can run this; there is no HTTP endpoint.
"""
import json
import os
import sys

from sqlalchemy.engine import make_url

from .models import Product, User
from .spending_scenarios import ensure_spending_cases
from .ux_fixtures import CASES, ensure_profiles, manifest_plan, other_records_hash


def demo_plan(manifest):
    if set(manifest) != {'schemaVersion', 'runId', 'createdAt', 'password'}:
        raise ValueError('Invalid personal demo manifest')
    pack = {key: manifest[key] for key in ('schemaVersion', 'runId', 'createdAt')}
    pack.update(packId='bryan-demo', passwords={case['id']: manifest['password'] for case in CASES})
    # Use the shared construction rules but persist only one profile.
    person = manifest_plan(pack)[0]
    person['case'] = dict(person['case'], name='Bryan')
    person['email'] = 'bryan.demo-'+manifest['runId']+'@nexqori.com'
    return pack, person


def ensure_demo(db, manifest):
    """The caller owns the transaction: profile, evidence and ledger commit together."""
    pack, person = demo_plan(manifest)
    before = other_records_hash(db, [person['userId']])
    existing = db.get(User, person['userId'])
    if existing and existing.name != 'Bryan':
        raise ValueError('This identity belongs to another profile; do not overwrite')
    if existing:
        # Identity and fixture markers remain authoritative after a local email change.
        person['email'] = existing.email
    result = ensure_profiles(db, pack, [person])
    scenario = ensure_spending_cases(db, person)
    if other_records_hash(db, [person['userId']]) != before:
        raise ValueError('Other profiles changed; abort demo creation')
    result['users'][0]['balanceMinor'] = db.get(Product, person['accountId']).balance_minor
    return result | {'currency': 'MXN', 'scenario': scenario}


def main():
    from .db import make_engine, make_sessions
    url = make_url(os.environ.get('DATABASE_URL', ''))
    if (os.environ.get('NEXQORI_LOCAL_VERIFY') != '1' or url.host != 'db'
            or url.database != 'nexqori' or url.get_backend_name() != 'postgresql'):
        raise ValueError('Only explicit local Nexqori Compose is supported')
    manifest = json.loads(sys.stdin.buffer.read(32769))
    engine = make_engine()
    try:
        with make_sessions(engine)() as db:
            with db.begin():
                result = ensure_demo(db, manifest)
        print(json.dumps(result, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Database errors can include credentials; return no raw diagnostics.
        print('Bryan demo not applied; check local configuration and manifest.', file=sys.stderr)
        raise SystemExit(1)
