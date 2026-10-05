"""Boundaries between Santiago's commands/documents and the current voice flow."""
import pytest
from backend.tests.test_api import setup, login
from backend.tests.test_workflow_chat import models
from backend.tests.test_voice import voice, start_body
from backend.tests.test_query_documents import query, body
from backend.chat_language import wrong_language
from backend.voice_summary import presentation

@pytest.mark.parametrize('locale,text',[('es','Es TX-PHONE-NEW'),('en','It is TX-PHONE-NEW'),('pt','É TX-PHONE-NEW')])
def test_reference_words_do_not_change_the_conversation_language(locale,text):
    assert not wrong_language(text,locale)
    if locale=='es': assert wrong_language('Open TX-PHONE-NEW',locale)


def test_document_closed_conversation_cannot_start_a_billed_call(voice,models):
    app,engine,provider=voice;client,_=login(app);_,control=models
    cid=query(client,control)
    result=client.post(f'/api/conversations/{cid}/documents',json=body('products_summary'))
    assert result.status_code==200
    started=client.post('/api/voice/sessions',json=start_body(conversationId=cid))
    assert started.status_code==409 and started.json()['error']=='conversation_closed'
    assert provider.created==[]


def test_local_navigation_does_not_repeat_previous_charge_findings(monkeypatch):
    from backend import voice_summary
    monkeypatch.setattr(voice_summary,'transaction_evidence',lambda *a:pytest.fail('Local navigation must not read prior evidence'))
    reply={'text':'UNTRUSTED','appCommand':None,'navigation':{'destination':'documents'},
           'conversation':{'transactionId':'TX-PRIVATE'},'flow':{'canRegister':True}}
    value=presentation(None,'customer',reply,'es')
    assert 'Mis documentos' in value['summary'] and value['comparison'] is None
    assert 'UNTRUSTED' not in value['summary'] and 'TX-PRIVATE' not in value['summary']


def test_voice_profile_request_opens_settings_without_mutating_profile(voice):
    app,_,provider=voice;client,_=login(app)
    before=client.get('/api/session').json()['user']
    identity=client.post('/api/voice/sessions',json=start_body()).json()['id']
    speech=app.state.voice.turn(identity,'profile','Cambia el tamaño de letra')
    reply=client.post(f'/api/voice/sessions/{identity}/heartbeat',json={}).json()['reply']
    assert reply['navigation']['route']=='/settings' and reply['appCommand'] is None
    assert 'Configuración' in speech and client.get('/api/session').json()['user']==before
    client.post(f'/api/voice/sessions/{identity}/close',json={})


def test_command_then_case_turn_keeps_message_order_when_clock_is_ahead(setup,models,monkeypatch):
    from datetime import datetime, timezone
    from backend import workflow_chat
    from backend.tests.test_workflow_chat import message
    app,_=setup;client,_=login(app);_,control=models
    cid=query(client,control)
    expected=client.get('/api/conversations/'+cid).json()['messages']
    monkeypatch.setattr(workflow_chat,'now',lambda:datetime(2030,1,1,tzinfo=timezone.utc))
    for text in ['Llévame al inicio','Quiero revisar mis movimientos del mes pasado']:
        response=client.post('/api/assistant/flow',json=message(message=text,conversationId=cid))
        assert response.status_code==200
        expected+=response.json()['messages']
    actual=client.get('/api/conversations/'+cid).json()['messages']
    assert [x['id'] for x in actual]==[x['id'] for x in expected]
