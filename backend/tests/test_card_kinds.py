"""Card kind is persisted metadata, independent of ownership and permissions."""
import pytest
from sqlalchemy.exc import IntegrityError
from backend.tests.test_api import setup, login
from backend.db import make_sessions
from backend.models import Product, CardProfile


def test_both_card_kinds_and_legacy_are_owned_and_consistent(setup):
    app, engine = setup
    with make_sessions(engine)() as db:
        db.get(Product, 'card-01').card_kind = 'credit'
        db.add(Product(id='debit-test', user_id='andrea', type='card', card_kind='debit', last4='4102', currency='MXN'))
        db.add(Product(id='legacy-test', user_id='andrea', type='card', last4='4103', currency='MXN'))
        db.flush()
        db.add(CardProfile(product_id='debit-test', user_id='andrea', provider_ref='debit-test', expiry_month=12, expiry_year=2030, settlement_product_id='account-01'))
        db.commit()
    client, _ = login(app)
    cards = {p['id']: p for p in client.get('/api/cards').json()['cards']}
    products = {p['id']: p for p in client.get('/api/bootstrap').json()['products']}
    for ident, kind in [('card-01', 'credit'), ('debit-test', 'debit'), ('legacy-test', None)]:
        assert cards[ident]['cardKind'] == products[ident]['cardKind'] == kind
        assert products[ident]['type'] == 'card'
    assert products['account-01']['cardKind'] is None
    other, _ = login(app, 'mateo')
    assert not {'card-01','debit-test','legacy-test'} & {p['id'] for p in other.get('/api/cards').json()['cards']}
    assert other.post('/api/cards/debit-test/reveal',json={'password':'irrelevant'}).status_code == 404


@pytest.mark.parametrize('kind,type_', [('cash','card'), ('debit','account'), ('credit','savings')])
def test_card_kind_rejects_invalid_or_non_card_assignments(setup, kind, type_):
    _, engine = setup
    with make_sessions(engine)() as db:
        db.add(Product(id='invalid-card', user_id='andrea', type=type_, card_kind=kind, last4='4100', currency='MXN'))
        with pytest.raises(IntegrityError):
            db.commit()
