from io import BytesIO
from uuid import uuid4
from pypdf import PdfReader
from backend.tests.test_chat_gateway import connected, send, snapshot, Providers
from backend.tests.test_api import setup, login
from nexqori_chat.contratos import Conversation, now
from nexqori_chat.codigo4_evidencia import missing_fields
from nexqori_chat.codigo6_documentos import generar_pdf


class DocumentProviders(Providers):
    def choice(self, stage, state, instructions, criteria):
        result = super().choice(stage, state, instructions, criteria)
        if stage == 'codigo3.intencion': result['label'] = 'documents'
        return result

    def generate(self, stage, state, instructions, schema):
        if stage == 'codigo4.extraer':
            text = state['latest_text']
            return {'understood': True, 'fields': [
                {'name': 'document_type', 'value': 'products_summary', 'quote': text},
                {'name': 'scope', 'value': 'all', 'quote': text}]}
        return super().generate(stage, state, instructions, schema)


def test_pdf_flow_download_session_isolation_and_no_writes(connected):
    app, engine, gateway = connected
    gateway.provider_factory = DocumentProviders
    client, _ = login(app, 'mateo')
    other, _ = login(app)
    same_owner, _ = login(app, 'mateo')
    before = snapshot(engine)
    message_id = str(uuid4())
    result = send(client, 'PDF resumen de todos mis productos', messageId=message_id).json()
    assert result['status'] == 'document_ready', result
    assert send(client, 'PDF resumen de todos mis productos', messageId=message_id).json() == result
    assert len(gateway.actions.documents) == 1
    route = '/api/assistant/documents/' + result['document']['id']
    pdf = client.get(route)
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF-')
    assert 'attachment' in pdf.headers['content-disposition'] and pdf.headers['cache-control'] == 'no-store'
    text = ''.join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert 'nexqori' in text.lower() and 'account-02' in text and 'account-01' not in text
    assert other.get(route).status_code == same_owner.get(route).status_code == 404
    assert snapshot(engine) == before
    gateway.actions.documents[result['document']['id']]['expires'] = 0
    assert client.get(route).status_code == 404


def test_human_context_only_shared_after_confirmation_and_two_way_chat(connected):
    app, engine, gateway = connected
    client, _ = login(app)
    other, _ = login(app, 'mateo')
    operator, _ = login(app, 'nora')
    before = snapshot(engine)
    result = send(client, 'persona').json()
    assert result['status'] == 'human_offer'
    ticket_id = result['handoff']['id']
    base = '/api/assistant/handoffs/' + ticket_id
    assert operator.get('/api/admin/chat-handoffs').json() == []
    assert client.get('/api/admin/chat-handoffs').status_code == 403
    assert other.post(base+'/confirm', json={'confirmed': True}).status_code == 404
    assert client.post(base+'/confirm', json={'confirmed': False}).status_code == 422
    assert client.post(base+'/confirm', json={'confirmed': True}, headers={'X-CSRF-Token':'wrong'}).status_code == 403
    assert client.post(base+'/confirm', json={'confirmed': True}).json()['status'] == 'queued'
    assert client.post(base+'/confirm', json={'confirmed': True}).json()['status'] == 'queued'
    received = operator.get('/api/admin/chat-handoffs').json()
    assert len(received) == 1 and received[0]['context']['messages'][-1]['text'] == 'persona'
    assert client.cookies['nexqori_session'] not in str(received)
    assert not {'session', 'user_id', 'persistence'} & received[0].keys()
    admin_route = '/api/admin/chat-handoffs/'+ticket_id+'/messages'
    payload = {'text':'Hola, soy tu agente. ¿En qué puedo ayudarte?', 'messageId':str(uuid4())}
    assert client.post(admin_route, json=payload).status_code == 403
    first = operator.post(admin_route, json=payload).json()
    assert first['status'] == 'active'
    assert operator.post(admin_route, json=payload).json() == first
    assert client.post(base+'/messages', json={'text':'Gracias, tengo una consulta.', 'messageId':str(uuid4())}).status_code == 200
    assert len(client.get('/api/assistant/handoffs').json()[0]['messages']) == 2
    assert other.get('/api/assistant/handoffs').json() == []
    assert snapshot(engine) == before
    assert client.post('/api/auth/logout', json={}).status_code == 200
    assert operator.get('/api/admin/chat-handoffs').json() == []


def test_document_requires_period_and_correct_selection():
    action = {'kind': 'document', 'requires': ['document_type','scope']}
    fields = {'document_type':'statement','scope':'selected'}
    assert set(missing_fields(action, fields)) == {'selection','period'}
    fields.update(product_id='account-02', all_history=True)
    assert missing_fields(action, fields) == []
    assert 'selection' in missing_fields(action, {'document_type':'requests_summary', 'scope':'selected', 'product_id':'account-02'})


def test_pdf_pagination_and_escape_untrusted_text():
    facts = [{'source_ref':'transactions:'+str(i), 'values': {'occurred_at':'2026-09-28T00:00:00+00:00',
        'merchant':'<b>Comercio & consulta</b> '+str(i), 'amount_display':'-12.50 MXN', 'status':'completed'}} for i in range(60)]
    packet = {'type':'statement', 'generated_at':now(), 'fields':{'all_history':True}, 'facts':facts}
    pdf = generar_pdf(packet, customer_name='Cliente de verificación', language='es')
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) > 1
    text = ''.join(p.extract_text() for p in reader.pages)
    assert '<b>Comercio & consulta</b> 59' in text
    assert all('nexqori' in p.extract_text().lower() for p in reader.pages)
