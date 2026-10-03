"""Opt-in en Docker: PostgreSQL real y proveedores falsos, sin inferencia externa."""
import os
import pytest
import psycopg
from fastapi.testclient import TestClient
from backend.db import make_engine, make_sessions
from backend.main import create_app
from backend.chat_gateway import ChatGateway
from backend.tests.test_chat_gateway import Providers, send, snapshot
from nexqori_chat.contratos import Trace, Conversation, now

pytestmark = pytest.mark.skipif(os.getenv('NEXQORI_TEST_POSTGRES') != '1',
    reason='Sólo ejecutar explícitamente en PostgreSQL local con fixtures')


def test_real_postgres_orchestrator_owner_filters_and_readonly_transaction():
    engine = make_engine()
    gateway = ChatGateway(engine, make_sessions(engine), mode='agent', provider_factory=Providers)
    origin = 'http://testserver'
    app = create_app(engine, [origin], False, chat_gateway=gateway)
    clients = []
    try:
        for email, password_var in [('andrea@nexqori.local', 'CUSTOMER_PASSWORD'),
                                    ('mateo@nexqori.local', 'SECOND_CUSTOMER_PASSWORD')]:
            client = TestClient(app)
            response = client.post('/api/auth/login', headers={'Origin': origin},
                json={'email': email, 'password': os.environ[password_var]})
            assert response.status_code == 200
            identity = response.json()
            client.headers.update({'Origin': origin, 'X-CSRF-Token': identity['csrfToken']})
            clients.append((client, identity['user']['id']))
        before = snapshot(engine)
        a, b = clients
        own = {p['id'] for p in b[0].get('/api/bootstrap').json()['products']}
        foreign = {p['id'] for p in a[0].get('/api/bootstrap').json()['products']}
        assert own and foreign and not own & foreign
        result = send(b[0], 'todas').json()
        assert result['status'] == 'answered'
        assert {f['values']['id'] for f in Providers.packets[-1]['rag']['facts']} == own
        token = b[0].cookies['nexqori_session']
        packet = gateway.repository.retrieve(token, b[1], 'balance', {'kind': 'read', 'query': 'products'},
            {'product_id': next(iter(foreign))}, Trace())
        assert packet['status'] == 'not_found' and packet['facts'] == []
        with pytest.raises(Exception) as denied:
            gateway.repository.authenticate(token, a[1])
        assert getattr(denied.value, 'code', None) == 'UNAUTHORIZED'
        conversation = Conversation(str(__import__('uuid').uuid4()), b[1])
        conversation.fields = {'document_type':'statement','scope':'all','all_history':True}
        conversation.messages = [{'language':'es'}]
        document = gateway.actions.document(conversation, token, gateway.repository, Trace())
        content, _ = gateway.actions.download(document['document']['id'], token, b[1])
        assert content.startswith(b'%PDF-')
        # Mismo modo transaccional del lector: PostgreSQL rechaza incluso UPDATE sin filas.
        with gateway.repository._connect() as conn, conn.transaction():
            conn.execute('SET TRANSACTION READ ONLY')
            with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
                conn.execute('UPDATE public.users SET role=role WHERE false')
        assert snapshot(engine) == before
    finally:
        for client, _ in clients:
            client.post('/api/auth/logout', json={})
            client.close()
        engine.dispose()
