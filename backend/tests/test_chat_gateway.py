"""Orquestador real con proveedores locales; no hace llamadas externas."""
from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.chat_gateway import ChatGateway
from backend.db import make_sessions
from backend.models import Base, Product
from backend.tests.test_api import setup, login

class FakeProviders:
    calls = []

    def __init__(self, settings, trace):
        pass

    def choice(self, stage, state, instructions, criteria):
        self.calls.append(stage)
        if stage == 'codigo2.tipo':
            label = 'reclamo' if state['messages'][-1]['text'] == 'reclamo' else 'solicitud'
        elif stage == 'codigo3.intencion':
            text = state['messages'][-1]['text']
            label = {'documento': 'documents', 'persona': 'human'}.get(text, 'balance')
        elif stage == 'codigo3.accion':
            label = 'navigate' if state['conversation']['messages'][-1]['text'] == 'abrir' else 'read'
        else:
            label = 'automatico'
        return {'label': label, 'probability': 1.0, 'confidence': 1.0, 'probabilities': {label: 1.0}, 'model': 'fake'}

    def generate(self, stage, state, instructions, schema):
        self.calls.append(stage)
        if stage == 'codigo4.extraer':
            text = state['latest_text']
            return {'understood': text != '???', 'fields': [{'name': 'scope', 'value': 'all', 'quote': 'todas'}] if 'todas' in text else []}
        if stage == 'codigo4.preguntar':
            return {'question': 'No entendÃ­ la respuesta. Â¿Una cuenta o todas?' if state['not_understood'] else 'Â¿Una cuenta o todas?'}
        return {'answer': 'El saldo es 10.00 MXN [F1].', 'citations': ['F1'], 'operations_executed': False}


class LocalRepository:
    """Doble SQLite; el lector PostgreSQL se verifica por separado."""
    def __init__(self, sessions):
        self.sessions = sessions
        self.gateway = None

    def authenticate(self, token, user_id):
        self.gateway.authorize(token, user_id)
        return user_id

    def retrieve(self, token, user_id, intent, action, fields, trace):
        self.authenticate(token, user_id)
        with self.sessions() as db:
            rows = db.scalars(select(Product).where(Product.user_id == user_id)).all()
        return {'status': 'ok', 'facts': [{'fact_id': f'F{i+1}', 'source_ref': 'products:'+p.id,
            'values': {'id': p.id, 'balance_minor': p.balance_minor}} for i, p in enumerate(rows)]}


class Providers(FakeProviders):
    packets = []
    def generate(self, stage, state, instructions, schema):
        if stage == 'codigo5.responder':
            self.packets.append(state)
            fact = state['rag']['facts'][0]
            return {'answer': str(fact['values']['balance_minor'])+' [F1]',
                'citations': ['F1'], 'operations_executed': False}
        return super().generate(stage, state, instructions, schema)


@pytest.fixture
def connected(setup):
    app, engine = setup
    repo = LocalRepository(make_sessions(engine))
    gateway = ChatGateway(engine, make_sessions(engine), mode='agent', repository=repo, provider_factory=Providers)
    repo.gateway = gateway
    app.state.chat_gateway = gateway
    Providers.calls = []
    Providers.packets = []
    return app, engine, gateway


def send(client, text, conversation=None, **extra):
    return client.post('/api/assistant', json={'message': text, 'locale': 'es',
        'conversationId': conversation, 'messageId': str(uuid4()), **extra})


def snapshot(engine):
    with engine.connect() as conn:
        return {t.name: [tuple(r) for r in conn.execute(select(t))] for t in Base.metadata.sorted_tables}


def test_conversation_scope_no_writes_and_public_allowlist(connected):
    app, engine, _ = connected
    client, _ = login(app, 'mateo')
    before = snapshot(engine)
    question = send(client, 'saldo').json()
    assert question['status'] == 'awaiting_user'
    result = send(client, 'todas', question['conversationId']).json()
    assert result['status'] == 'answered', result
    assert set(result) == {'text', 'status', 'conversationId', 'traceId', 'destination', 'navigation', 'execution_authorized'}
    assert result['navigation'] is None and result['execution_authorized'] is False
    packet = Providers.packets[-1]
    assert {f['values']['id'] for f in packet['rag']['facts']} == {'account-02'}
    assert client.cookies['nexqori_session'] not in str(packet)
    assert snapshot(engine) == before


def test_identity_injection_and_cross_session_conversation(connected):
    app, _, _ = connected
    client, _ = login(app)
    other, _ = login(app, 'mateo')
    same_user, _ = login(app)
    first = send(client, 'saldo').json()
    for browser in (other, same_user):
        assert send(browser, 'todas', first['conversationId']).status_code == 409
    for extra in ({'user_id': 'customer-02'}, {'session_token': 'forged'}, {'role': 'admin'}, {'fields': {'scope': 'all'}}):
        assert send(client, 'todas', **extra).status_code == 422
    assert send(client, 'todas', **{'messageId': 'bad'}).status_code == 422
    client.headers['X-CSRF-Token'] = 'bad'
    assert send(client, 'todas').status_code == 403


def test_replay_and_pending_operations_do_not_write(connected):
    app, engine, _ = connected
    client, _ = login(app)
    before = snapshot(engine)
    message_id = str(uuid4())
    first = send(client, 'todas', messageId=message_id)
    count = len(Providers.calls)
    assert send(client, 'todas', messageId=message_id).json() == first.json()
    assert len(Providers.calls) == count
    assert send(client, 'otro texto', messageId=message_id).status_code == 409
    for text in ('reclamo', 'abrir'):
        result = send(client, text).json()
        assert result['status'] == 'pending_implementation', result
        assert result['navigation'] is None
    assert snapshot(engine) == before


def test_failure_stops_and_clears_public_conversation(connected):
    app, engine, gateway = connected
    class Failing(Providers):
        def choice(self, *args):
            raise RuntimeError('private error / credentials must never reach browser')
    gateway.provider_factory = Failing
    client, _ = login(app)
    before = snapshot(engine)
    result = send(client, 'todas').json()
    assert result['status'] == 'error' and result['conversationId'] is None
    assert 'private error' not in str(result)
    assert result['traceId']
    assert snapshot(engine) == before


def test_revocation_during_provider_call_blocks_response(connected):
    app, engine, gateway = connected
    client, _ = login(app)
    class Revoking(Providers):
        def generate(self, stage, *args):
            result = super().generate(stage, *args)
            if stage == 'codigo5.responder':
                assert client.post('/api/auth/logout', json={}).status_code == 200
            return result
    gateway.provider_factory = Revoking
    assert send(client, 'todas').status_code == 401
    assert gateway.entries == {}


def test_three_ununderstood_replies_keep_context_then_pending_human(connected):
    app, _, _ = connected
    client, _ = login(app)
    result = send(client, 'saldo').json()
    for _ in range(2):
        result = send(client, '???', result['conversationId']).json()
        assert result['status'] == 'awaiting_user'
    result = send(client, '???', result['conversationId']).json()
    assert result['status'] == 'human_offer'
    assert result['handoff']['id']
