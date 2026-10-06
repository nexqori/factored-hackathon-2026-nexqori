import json
from uuid import uuid4
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from backend.db import make_sessions
from backend.models import ServiceAgreement, Transaction
from backend.tests.test_api import setup, login, ORIGIN
from backend.tests.test_workflow_chat import models, message
from backend.tests.test_service_agreements import prepared
from backend.tests.test_voice import voice, start_body, wait_until
from backend.voice_summary import presentation


@pytest.mark.parametrize('locale',['es','en','pt'])
def test_recorded_plan_summary_chart_and_privacy(setup,locale):
    _,engine=setup;pack,person,scenario=prepared(engine);txid=scenario['transactionIds'][1]
    reply={'text':'UNTRUSTED_RESPONSE', 'conversation':{'transactionId':txid},'flow':{'canRegister':True,'missing_fields':[]}}
    with make_sessions(engine)() as db:
        result=presentation(db,person['userId'],reply,locale)
        assert result['comparison']=={'basis':'agreement','baselineMinor':29900,'currentMinor':45900,'differenceMinor':16000,'currency':'MXN','count':5,'verdict':'above-base'}
        speech=result['summary']
        for value in ('459.00','299.00','160.00','supervisor'):assert value in speech
        for value in (txid,'UNTRUSTED_RESPONSE','Empresa Telefónica',person['email']):assert value not in speech
        assert len(speech.split())<120
        with pytest.raises(HTTPException) as err:presentation(db,'mateo',reply,locale)
        assert err.value.status_code==404
        terms=db.scalar(select(ServiceAgreement).where(ServiceAgreement.user_id==person['userId']))
        terms.monthly_minor=45900;db.flush()
        assert presentation(db,person['userId'],reply,locale)['comparison']['verdict']=='within-base'


def test_insufficient_history_does_not_claim_customer_wrong(setup):
    app,engine=setup;client,_=login(app)
    with make_sessions(engine)() as db:
        result=presentation(db,'andrea',{'conversation':{'transactionId':'TX-1002'},'flow':{}},'es')
        assert result['comparison'] is None
        assert 'No tengo suficientes' in result['summary']


@pytest.mark.parametrize('fallback',['needs-clarification','out-of-scope'])
def test_subtype_clarification_still_searches_payment_clues(setup,models,fallback):
    app,_=setup;client,_=login(app);calls,control=models;control['intent']=fallback
    reply=client.post('/api/assistant/flow',json=message(message='Tengo un problema con el pago de 189 MXN')).json()
    assert reply['flow']['suggestedTransaction']['id']=='TX-1002'
    assert reply['navigation']['destination']=='movements'
    assert not reply['conversation']['transactionId']
    assert not reply['flow']['canRegister']


@pytest.mark.parametrize('locale',['es','en','pt'])
def test_voice_confirmed_plan_case_announced_once_and_pending_not_refunded(voice,models,locale):
    app,engine,provider=voice;pack,person,scenario=prepared(engine)
    client=TestClient(app)
    logged=client.post('/api/auth/login',headers={'Origin':ORIGIN},json={'identifier':person['email'],'password':pack['passwords']['cargo']}).json()
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':logged['csrfToken']})
    txid=scenario['transactionIds'][1]
    before=client.get('/api/bootstrap').json()
    started=client.post('/api/voice/sessions',json=start_body(locale=locale,transactionId=txid)).json()
    identity=started['id'];cid=started['conversationId']
    provider.socket.events.put({'type':'session.input_transcript.delta','event_id':'input','delta':{'es':'Me cobraron de más en el teléfono','en':'I was overcharged for my phone','pt':'Cobraram a mais no telefone'}[locale],'start_ms':0,'end_ms':100})
    provider.socket.events.put({'type':'session.delegation.created','delegation':{'id':'find','target':'client'},'offset_ms':100})
    result=wait_until(lambda:(v if (v:=client.post(f'/api/voice/sessions/{identity}/heartbeat',json={}).json()).get('revision')==1 else None))
    assert result['reply']['flow']['canRegister'], result['reply']
    assert result['reply']['voiceSummary']['comparison']['differenceMinor']==16000
    wait_until(lambda:any('160.00' in e.get('content','') for e in provider.socket.sent))
    preview=client.get(f'/api/conversations/{cid}/claim-preview?locale={locale}').json()
    body={'confirmed':True,'details':preview['summary'],'locale':locale,'previewToken':preview['previewToken'],'requestKey':str(uuid4())}
    claim=client.post(f'/api/conversations/{cid}/claim',json=body)
    assert claim.status_code==200,claim.text
    rid=claim.json()['id']
    assert client.post(f'/api/conversations/{cid}/claim',json=body).json()['id']==rid
    wait_until(lambda:any(rid in e.get('content','') for e in provider.socket.sent))
    assert len([e for e in provider.socket.sent if rid in e.get('content','')])==1
    assert app.state.voice.registration_notice(identity) is None
    trace=client.get(f'/api/requests/{rid}/trace').json()
    assert trace['request']['status']=='received'
    after=client.get('/api/bootstrap').json()
    for key in ('products','transactions'):assert after[key]==before[key]
    client.post(f'/api/voice/sessions/{identity}/close',json={})


def test_specific_overcharge_reclassifies_vague_payment_without_losing_selected_record(setup,models):
    app,_=setup;client,_=login(app);calls,control=models
    control['intent']='payment-status'
    first=client.post('/api/assistant/flow',json=message(message='Revisa el estado del pago',transactionId='TX-1002')).json()
    cid=first['conversation']['id'];control['intent']='incorrect-charge'
    revised=client.post('/api/assistant/flow',json=message(conversationId=cid,message='Me cobraron de más; esperaba 100 MXN')).json()
    assert revised['flow']['jev']['intent']=='incorrect-charge'
    assert revised['conversation']['transactionId']=='TX-1002' and revised['flow']['canRegister']
    assert revised['conversation']['id']==cid
    assert 'Stream Plus' not in json.dumps(calls)


@pytest.mark.parametrize('locale,text', [
    ('es', 'Sí, ese es el que quiero revisar y poner una... solicitud de devolución, no lo'),
    ('es', 'pasar Sí, no reconozco ese cobro. ¿Puedes hacerme un reclamo'),
    ('en', 'Yes, I do not recognize that charge. Please prepare a complaint.'),
    ('pt', 'Sim, não reconheço essa cobrança. Pode preparar uma reclamação?'),
])
def test_real_voice_proposal_compound_confirmation_and_review(voice, models, locale, text):
    app, engine, provider = voice; pack, person, scenario = prepared(engine)
    calls, control = models; control['intent'] = 'unrecognized-charge'
    client = TestClient(app)
    logged = client.post('/api/auth/login', headers={'Origin': ORIGIN}, json={'identifier': person['email'], 'password': pack['passwords']['cargo']}).json()
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': logged['csrfToken']})
    started = client.post('/api/voice/sessions', json=start_body(locale=locale)).json()
    identity, cid = started['id'], started['conversationId']
    before = client.get('/api/bootstrap').json()
    def turn(index, message):
        provider.socket.events.put({'type':'session.input_transcript.delta','event_id':'input-'+str(index),'delta':message,'start_ms':index*1000,'end_ms':index*1000+100})
        provider.socket.events.put({'type':'session.delegation.created','delegation':{'id':'turn-'+str(index),'target':'client'},'offset_ms':index*1000+100})
        return wait_until(lambda:(v['reply'] if (v:=client.post(f'/api/voice/sessions/{identity}/heartbeat',json={}).json()).get('revision')==index else None))
    first = turn(1, {'es':'Tengo un cargo no reconocido del teléfono','en':'I do not recognize my phone charge','pt':'Não reconheço a cobrança do telefone'}[locale])
    txid = first['flow']['suggestedTransaction']['id']
    assert first['conversation']['transactionId'] is None
    result = turn(2, text)
    assert result['conversation']['transactionId'] == txid
    assert result['flow']['canRegister'] and result['flow']['reviewRequestKey']
    assert not result['flow']['suggestedTransaction']
    speech = result['voiceSummary']['summary']
    assert '299.00' in speech and '459.00' in speech and '160.00' in speech
    assert any(word in speech for word in ('promedian', 'average', 'média'))
    assert result['voiceSummary']['comparison']['differenceMinor'] == 16000
    preview = client.get(f'/api/conversations/{cid}/claim-preview?locale={locale}').json()
    assert txid in preview['summary']
    assert client.get('/api/bootstrap').json()['requests'] == before['requests']
    later = turn(3, {'es':'Agrega que no autoricé servicios extra','en':'Add that I did not authorize extras','pt':'Acrescente que não autorizei extras'}[locale])
    assert later['conversation']['transactionId'] == txid
    assert not later['flow']['suggestedTransaction']
    assert later['flow']['reviewRequestKey'] == result['flow']['reviewRequestKey']
    assert txid not in json.dumps(calls)
    client.post(f'/api/voice/sessions/{identity}/close',json={})


def test_requesting_preview_keeps_previously_supplied_amount_without_reasking(setup, models):
    app, _ = setup; client, _ = login(app); calls, control = models
    first = client.post('/api/assistant/flow', json=message(transactionId='TX-1002')).json()
    cid = first['conversation']['id']
    ready = client.post('/api/assistant/flow', json=message(conversationId=cid, message='Esperaba 100 MXN')).json()
    assert ready['flow']['canRegister']; count = len(calls)
    reply = client.post('/api/assistant/flow', json=message(conversationId=cid, message='¿Puedes hacerme un reclamo?')).json()
    assert reply['flow']['canRegister'] and reply['flow']['reviewRequestKey']
    assert reply['flow']['missing_fields'] == []
    assert len(calls) == count
    preview = client.get(f'/api/conversations/{cid}/claim-preview').json()
    assert '100 MXN' in preview['summary']


def test_resuming_refunded_case_announces_credit_and_opens_case_first(voice, models):
    from backend.tests.test_operations import approve_case, approve_payload
    app, _, provider = voice; customer, _ = login(app); admin, _ = login(app, 'nora')
    _, control = models; control['intent']='unrecognized-charge'
    first=customer.post('/api/assistant/flow',json=message(transactionId='TX-1002')).json()
    cid=first['conversation']['id']
    claim=customer.post('/api/conversations/'+cid+'/claim',json={'confirmed':True,'details':'Cargo no reconocido para revisar.','requestKey':str(uuid4())}).json()
    approve_case(admin,claim['id'])
    refund=admin.get('/api/admin/requests/'+claim['id']+'/refund').json()['refund']
    credit=admin.post('/api/admin/refunds/'+refund['id']+'/decision',json=approve_payload()).json()['creditTransactionId']
    before=customer.get('/api/bootstrap').json()
    started=customer.post('/api/voice/sessions',json=start_body(conversationId=cid)).json()
    result=wait_until(lambda:(v.get('reply') if (v:=customer.post('/api/voice/sessions/'+started['id']+'/heartbeat',json={}).json()).get('revision') else None))
    assert result['navigation']['route']=='/complaints?case='+claim['id']
    assert 'reembolso realizado' in result['voiceSummary']['summary']
    assert customer.get('/api/bootstrap').json()['transactions']==before['transactions']
    customer.post('/api/voice/sessions/'+started['id']+'/close',json={})


@pytest.mark.parametrize('phrase', ['No, enviémoslo a revisión', 'Confirmar y enviar', 'Okay, send it like it is', 'Yes, send it', 'Okay Send the refund request for review, please', 'Sim, envie assim'])
def test_real_reported_sequence_submits_displayed_draft_once(voice, models, phrase, monkeypatch):
    action_contexts=[]
    def propose(text,locale,awaiting=False):
        action_contexts.append((text,awaiting))
        return 'submit-claim' if text==phrase else 'continue'
    monkeypatch.setattr('backend.voice.classify_action', propose)
    app, engine, _ = voice; client, _ = login(app)
    _, control = models; control['intent'] = 'unrecognized-charge'
    started = client.post('/api/voice/sessions', json=start_body()).json()
    runtime = app.state.voice; identity = started['id']; cid = started['conversationId']
    runtime.turn(identity, 'proposal', 'Tengo un problema con un cargo no reconocido de Stream Plus')
    speech = runtime.turn(identity, 'selection', 'Sí, ese es el que quiero revisar')
    reply = client.post(f'/api/voice/sessions/{identity}/heartbeat', json={}).json()['reply']
    assert reply['navigation']['route'] == '/complaints'
    assert reply['flow']['canRegister'] and reply['flow']['reviewRequestKey']
    before = client.get('/api/bootstrap').json()
    # Saying send without a displayed draft may only open the draft.
    runtime.turn(identity, 'not-shown', phrase)
    assert client.get('/api/bootstrap').json()['requests'] == before['requests']
    preview = client.get(f'/api/conversations/{cid}/claim-preview?locale=es').json()
    ack = client.post(f'/api/conversations/{cid}/claim-review', json={
        'previewToken':preview['previewToken'], 'details':preview['summary'], 'ready':True, 'locale':'es'})
    assert ack.status_code == 200, ack.text
    speech = runtime.turn(identity, 'submit', phrase)
    assert action_contexts[-1] == (phrase, True)
    assert (phrase, False) in action_contexts
    reply = client.post(f'/api/voice/sessions/{identity}/heartbeat', json={}).json()['reply']
    rid = reply['flow']['requestId']; assert rid
    assert reply['navigation']['route'] == '/complaints?case='+rid
    assert 'Gracias por avisarnos' in speech and 'promedio' not in speech
    assert runtime.registration_notice(identity) is None
    runtime.turn(identity, 'submit', phrase)
    after = client.get('/api/bootstrap').json()
    assert len(after['requests']) == len(before['requests']) + 1
    assert after['transactions'] == before['transactions']
    assert after['products'] == before['products']
    assert client.get(f'/api/requests/{rid}/trace').json()['request']['status'] == 'received'
    client.post(f'/api/voice/sessions/{identity}/close',json={})


def test_editing_draft_revokes_voice_submission(voice, models, monkeypatch):
    monkeypatch.setattr('backend.voice.classify_action', lambda *a: 'submit-claim')
    app, _, _ = voice; client, _ = login(app)
    _, control = models; control['intent'] = 'unrecognized-charge'
    started = client.post('/api/voice/sessions', json=start_body(transactionId='TX-1002')).json()
    identity, cid = started['id'], started['conversationId']; runtime=app.state.voice
    runtime.turn(identity, 'prepare', 'No reconozco ese cargo')
    preview = client.get(f'/api/conversations/{cid}/claim-preview?locale=es').json()
    for ready in (True,False):
        assert client.post(f'/api/conversations/{cid}/claim-review', json={
            'previewToken':preview['previewToken'],'details':preview['summary'],'ready':ready,'locale':'es'}).status_code == 200
    before=client.get('/api/bootstrap').json()['requests']
    runtime.turn(identity,'send-while-editing','Confirmar y enviar')
    assert client.get('/api/bootstrap').json()['requests']==before
    client.post(f'/api/voice/sessions/{identity}/close',json={})


@pytest.mark.parametrize('guard_status', ['blocked','uncertain','unavailable'])
def test_voice_submission_guard_failure_never_registers(voice, models, monkeypatch, guard_status):
    from backend import voice as voice_module, workflow_chat
    app, _, _ = voice; client, _ = login(app)
    _, control = models; control['intent'] = 'unrecognized-charge'
    started = client.post('/api/voice/sessions', json=start_body(transactionId='TX-1002')).json()
    identity, cid = started['id'], started['conversationId']; runtime=app.state.voice
    runtime.turn(identity,'prepare','No reconozco ese cargo')
    preview=client.get(f'/api/conversations/{cid}/claim-preview?locale=es').json()
    assert client.post(f'/api/conversations/{cid}/claim-review',json={
        'previewToken':preview['previewToken'],'details':preview['summary'],'ready':True,'locale':'es'}).status_code==200
    before=client.get('/api/bootstrap').json()['requests']
    monkeypatch.setattr(voice_module,'classify_action',lambda *a:'submit-claim')
    monkeypatch.setattr(voice_module,'inspect_prompt',lambda *a,**k:{'status':guard_status})
    monkeypatch.setattr(workflow_chat,'inspect_prompt',lambda *a,**k:{'status':guard_status})
    runtime.turn(identity,'submit','Confirmar y enviar')
    assert client.get('/api/bootstrap').json()['requests']==before
    reply=client.post(f'/api/voice/sessions/{identity}/heartbeat',json={}).json()['reply']
    assert reply['guard']['status']==guard_status and not reply['flow']['canRegister']
    assert not reply['navigation']
    client.post(f'/api/voice/sessions/{identity}/close',json={})
