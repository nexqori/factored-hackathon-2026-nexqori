from fastapi.testclient import TestClient
from sqlalchemy import select, func, inspect
from backend.tests.test_api import setup, login, PASSWORDS
from backend.db import make_sessions
from backend.models import CardProfile, AuditEvent


def test_cvv_window_and_short_reveal_grant(setup,monkeypatch):
    from backend import cards
    app,engine=setup;client,_=login(app);monkeypatch.setenv('CARD_PROVIDER','local_fixture')
    stamp=[int(cards.time.time())//900*900+899]
    monkeypatch.setattr(cards.time,'time',lambda:stamp[0])
    route='/api/cards/card-01'
    first=client.post(route+'/reveal',json={'password':PASSWORDS[0]}).json()
    assert first['cvvExpiresAt']==stamp[0]+1
    token={'revealToken':first['revealToken']}
    assert client.post(route+'/cvv',json=token).json()['cvv']==first['cvv']
    stamp[0]+=1
    second=client.post(route+'/cvv',json=token)
    assert second.status_code==200 and second.json()['cvv']!=first['cvv']
    assert second.json()['cvvExpiresAt']==stamp[0]+900
    assert 'number' not in second.text and 'expiryYear' not in second.text
    assert client.post(route+'/cvv',json={'revealToken':token['revealToken'][:-1]+('0' if token['revealToken'][-1]!='0' else '1')}).status_code==403
    assert client.post(route+'/cvv',json=token,headers={'X-CSRF-Token':'bad'}).status_code==403
    stamp[0]+=59
    assert client.post(route+'/cvv',json=token).status_code==403
    with make_sessions(engine)() as db:
        assert all(first['cvv'] not in (r.action or '') for r in db.scalars(select(AuditEvent)))


def test_other_local_card_can_reveal_with_own_last_four_and_block_revokes_grant(setup,monkeypatch):
    from backend.models import Product
    from uuid import uuid4
    app,engine=setup;client,_=login(app);monkeypatch.setenv('CARD_PROVIDER','local_fixture')
    with make_sessions(engine)() as db:
        db.add(Product(id='verify-card-extra',user_id='andrea',type='card',last4='1122',balance_minor=None));db.flush()
        db.add(CardProfile(product_id='verify-card-extra',user_id='andrea',provider_ref='verify-card-extra',expiry_month=12,expiry_year=2029));db.commit()
    assert all(c['canReveal'] for c in client.get('/api/cards').json()['cards'])
    response=client.post('/api/cards/verify-card-extra/reveal',json={'password':PASSWORDS[0]})
    assert response.status_code==200
    data=response.json();assert data['number'].endswith('1122') and len(data['number'])==16
    other,_=login(app,'mateo')
    assert other.post('/api/cards/verify-card-extra/cvv',json={'revealToken':data['revealToken']}).status_code==404
    assert client.post('/api/cards/card-01/cvv',json={'revealToken':data['revealToken']}).status_code==403
    blocked=client.post('/api/cards/verify-card-extra/block',json={'password':PASSWORDS[0],'confirmed':True,'requestKey':str(uuid4())})
    assert blocked.status_code==200,blocked.text
    assert client.post('/api/cards/verify-card-extra/cvv',json={'revealToken':data['revealToken']}).json()['error']=='card_blocked'


def test_card_details_require_owner_role_csrf_and_password(setup, monkeypatch):
    app, engine = setup
    monkeypatch.setenv("CARD_PROVIDER", "local_fixture")
    assert TestClient(app).get('/api/cards').status_code == 401
    client, _ = login(app)
    cards = client.get('/api/cards')
    assert cards.json()['cards'][0]['expiryYear'] is None
    assert 'cvv' not in cards.text and 'number' not in cards.text
    route = '/api/cards/card-01/reveal'
    payload = {'password': PASSWORDS[0]}
    assert client.post(route, json=payload, headers={'X-CSRF-Token': 'bad'}).status_code == 403
    assert client.post(route, json={'password': 'incorrect'}).json()['error'] == 'card_password'
    result = client.post(route, json=payload)
    assert result.status_code == 200
    assert result.headers['cache-control'] == 'no-store'
    value = result.json()
    assert value['expiryYear'] == 2029 and value['expiryMonth'] == 12
    assert value['number'] == '4000056655665556' and len(value['cvv']) == 3
    from time import time
    assert 58 <= value['expiresAt'] - time() <= 60
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == 'card_details_viewed')) == 1
        assert all(c['name'] not in ('number', 'cvv', 'pan') for c in inspect(engine).get_columns('card_profiles'))
    other, _ = login(app, 'mateo')
    assert other.get('/api/cards').json() == {'cards': []}
    assert other.post(route, json={'password': PASSWORDS[2]}).status_code == 404
    admin, _ = login(app, 'nora')
    assert admin.get('/api/cards').status_code == 403
    assert admin.post(route, json={'password': PASSWORDS[1]}).status_code == 403


def test_disabled_expired_and_rate_limited_card_reveal(setup, monkeypatch):
    app, engine = setup
    client, _ = login(app)
    monkeypatch.delenv('CARD_PROVIDER', raising=False)
    route = '/api/cards/card-01/reveal'; payload = {'password': PASSWORDS[0]}
    assert client.get('/api/cards').json()['cards'][0]['canReveal'] is False
    assert client.post(route, json=payload).status_code == 503
    monkeypatch.setenv('CARD_PROVIDER', 'local_fixture')
    with make_sessions(engine)() as db:
        db.get(CardProfile, 'card-01').expiry_year = 2000; db.commit()
    assert client.post(route, json=payload).json()['error'] == 'card_expired'
    for _ in range(3):
        assert client.post(route, json={'password': 'wrong'}).status_code == 403
    assert client.post(route, json=payload).status_code == 429
