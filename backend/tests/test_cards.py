from fastapi.testclient import TestClient
from sqlalchemy import select, func, inspect
from backend.tests.test_api import setup, login, PASSWORDS
from backend.db import make_sessions
from backend.models import CardProfile, AuditEvent


def test_card_details_require_owner_role_csrf_and_password(setup, monkeypatch):
    app, engine = setup
    monkeypatch.setenv("CARD_PROVIDER", "local_fixture")
    assert TestClient(app).get('/api/cards').status_code == 401
    client, _ = login(app)
    cards = client.get('/api/cards')
    assert cards.json()['cards'][0]['expiryYear'] == 2029
    assert 'cvv' not in cards.text and 'number' not in cards.text
    route = '/api/cards/card-01/reveal'
    payload = {'password': PASSWORDS[0]}
    assert client.post(route, json=payload, headers={'X-CSRF-Token': 'bad'}).status_code == 403
    assert client.post(route, json={'password': 'incorrect'}).json()['error'] == 'card_password'
    result = client.post(route, json=payload)
    assert result.status_code == 200
    assert result.headers['cache-control'] == 'no-store'
    value = result.json()
    assert value['number'] == '0000000000008942' and len(value['cvv']) == 3
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
