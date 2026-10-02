"""Ownership, bank reads and provenance through the actual LAB API and engine."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from intent_lab import api, bank_context as bank, workflow_editor as editor
from test_providers import private_config
from test_luna_dialogue import enable
from test_workflow_steps import models, master, start, advance, result_of, replay

CLIENT=httpx.Client
TOKEN='a'*64
CSRF='private-csrf-never-persist'


@pytest.fixture
def gateway(monkeypatch):
    calls=[]
    control={'expired':False,'fail':False,'linked':True}
    def handler(request):
        assert request.url.host=='127.0.0.1' and request.url.port==5180
        assert request.headers['origin']=='http://localhost:5180'
        cookie=request.headers.get('cookie','')
        owner='owner-2' if 'b'*64 in cookie else 'owner-1'
        if control['expired']: return httpx.Response(401)
        if request.url.path=='/api/session':
            return httpx.Response(200,json={'user':{'id':owner,'name':'Verificación','role':'admin' if 'c'*64 in cookie else 'customer'},'csrfToken':CSRF})
        assert request.url.path=='/api/assistant/tools/read' and request.method=='POST'
        assert request.headers['x-csrf-token']==CSRF
        body=json.loads(request.content);calls.append(body)
        assert body['tool'] in bank.tools_for(body['intent']) and bank.TOOLS[body['tool']]['kind']=='read'
        assert set(body)<= {'intent','tool','locale','referenceId'}
        if control['fail']: return httpx.Response(503)
        tool=body['tool'];reference=body.get('referenceId')
        tx={'id':'tx-owner-1','merchant':'COMERCIO REGISTRO PRIVADO','date':'2026-09-30T14:00:00+00:00','amountMinor':42550,'currency':'MXN','status':'pending'}
        if reference and (owner!='owner-1' or reference not in ('tx-owner-1','NQ-OWNER1')): return httpx.Response(404)
        data={'read-transactions':{'transactions':[tx] if owner=='owner-1' else [],'hasMore':False,'limit':20},
              'read-transaction-evidence':{'source':'nexqori_records','externalProcessorLogs':False,'transaction':tx,'request':{'id':'NQ-OWNER1','status':'pending'} if control['linked'] else None,'refund':None,'events':[{'action':'request_created','at':'2026-10-01T10:00:00Z'}]},
              'read-request-status':{'request':{'id':'NQ-OWNER1','status':'pending'}},
              'read-cards':{'cards':[]},'read-problem-contract':{'contract':{'id':body['intent']}}}[tool]
        return httpx.Response(200,json={'tool':tool,'intent':body['intent'],'source':'nexqori_records','status':'executed','data':data,'auditEventId':'audit-'+str(len(calls)),'executed_operations':[]})
    monkeypatch.setattr(bank,'http_client',lambda **kw:CLIENT(transport=httpx.MockTransport(handler),**kw))
    return calls,control


def customer():
    client=TestClient(api.app);client.cookies.set(bank.COOKIE,TOKEN,path='/api')
    return client


def bank_start(client,record,**extra):
    response=client.post('/api/lab-api/editor/workflows/'+record['id']+'/run-stream',json={
        'revision':record['revision'],'messages':[{'role':'user','content':'Quiero revisar el movimiento'}],
        'bank':{'transaction_id':'tx-owner-1'},**extra})
    return result_of(response)


@pytest.mark.parametrize('language',['es','en','pt'])
@pytest.mark.parametrize('intent',['unrecognized-charge','incorrect-charge','payment-status'])
def test_context_uses_owned_records_asks_only_missing_and_keeps_secrets_private(private_config,monkeypatch,gateway,language,intent):
    enable(private_config);provider_calls=models(monkeypatch,intent=intent)
    client=customer();value=bank_start(client,master(client),language=language)
    assert value['missing_fields']==(['difference'] if intent=='incorrect-charge' else [])
    assert value['state']==('ask_customer' if intent=='incorrect-charge' else 'review_in_bank')
    assert value['bank_context']['owner_id']=='owner-1'
    assert {f['field'] for f in value['verified_facts']}==({'movement','date','status'} if intent=='payment-status' else {'movement','date','amount'})
    assert all(f['source']=='nexqori_records' and f['audit_event_id'] for f in value['verified_facts'])
    assert value['executed_operations']==[] and value['authorizes_execution'] is False
    assert any(t['tool']=='read-transaction-evidence' for t in value['executed_tools'])
    evidence=value['bank_evidence'];assert not evidence['application_error_logs'] and not evidence['external_processor_logs']
    assert len(provider_calls)==3 and 'COMERCIO REGISTRO PRIVADO' not in json.dumps(provider_calls)
    assert 'audit-' not in json.dumps(provider_calls)
    files=''.join(path.read_text(encoding='utf-8') for path in private_config.rglob('*.json'))
    assert TOKEN not in files and CSRF not in files
    before=len(gateway[0]);execution_id=value['execution']['id']
    assert client.get('/api/lab-api/editor/executions/'+execution_id).json()==value
    assert len(gateway[0])==before  # viewing checks identity but never re-runs a read tool
    assert all(r['id']!=value['id'] for r in client.get('/lab-api/runs').json()['runs'])
    assert client.get('/api/lab-api/runs/'+value['id']).status_code==200
    other=customer();other.cookies.set(bank.COOKIE,'b'*64,path='/api')
    assert other.get('/api/lab-api/editor/executions/'+execution_id).status_code==404
    assert other.get('/api/lab-api/runs/'+value['id']).status_code==404
    payload={'version':value['execution']['version'],'node_id':'context'}
    assert other.post('/api/lab-api/editor/executions/'+execution_id+'/replay',json=payload).status_code==404
    assert other.post('/api/lab-api/editor/executions/'+execution_id+'/advance',json=payload).status_code==404
    assert len(gateway[0])==before


def test_requires_customer_session_and_forbids_forged_ownership(private_config,gateway):
    client=TestClient(api.app);record=master(client)
    assert client.post('/api/lab-api/editor/bank/records',json={}).status_code==401
    client.cookies.set(bank.COOKIE,'c'*64,path='/api')
    assert client.post('/api/lab-api/editor/bank/records',json={}).status_code==403
    assert client.post('/api/lab-api/editor/workflows/'+record['id']+'/run',json={'revision':1,'messages':[{'role':'user','content':'Consulta'}],'bank':{'owner_id':'someone'}}).status_code==422
    client=customer()
    assert client.post('/api/lab-api/editor/bank/records',json={},headers={'Origin':'https://outside.invalid'}).status_code==403
    data=client.post('/api/lab-api/editor/bank/records',json={}).json()
    assert data['user']['id']=='owner-1' and len(data['transactions'])==1
    assert CSRF not in json.dumps(data) and TOKEN not in json.dumps(data)


def test_missing_reference_waits_and_selection_can_continue_without_inventing_message(private_config,monkeypatch,gateway):
    enable(private_config);calls=models(monkeypatch,assessments=[{'assessment':'continue','observations':[]}]*2)
    client=customer();value=bank_start(client,master(client),bank={})
    assert 'transaction_id' in value['missing_fields'] and value['execution']['phase']=='waiting_reply'
    old_messages=value['messages'];state=value['execution']
    r=client.post('/api/lab-api/editor/executions/'+state['id']+'/advance',json={'version':state['version'],'node_id':'context','mode':'full','bank':{'transaction_id':'tx-owner-1'}})
    result=result_of(r)
    assert result['state']=='review_in_bank' and not result['missing_fields']
    assert result['messages'][:-1]==old_messages and len(calls)==4
    assert result['triage']==value['triage'] and result['jev']==value['jev']


@pytest.mark.parametrize('mode',['foreign','expired','unavailable','mismatch'])
def test_bank_failure_cannot_become_sufficient_evidence(private_config,monkeypatch,gateway,mode):
    enable(private_config);calls=models(monkeypatch)
    client=customer();record=master(client)
    value=bank_start(client,record,mode='step')
    state=value['execution']
    if mode=='expired':
        gateway[1]['expired']=True
        assert client.post('/api/lab-api/editor/executions/'+state['id']+'/advance',json={'version':state['version'],'node_id':state['next_node_id']}).status_code==401
        assert not calls
        return
    if mode=='unavailable':gateway[1]['fail']=True
    selection={'transaction_id':'foreign'} if mode=='foreign' else {'transaction_id':'tx-owner-1','request_id':'NQ-OTHER'} if mode=='mismatch' else {'transaction_id':'tx-owner-1'}
    value=bank_start(client,record,bank=selection)
    assert value['trace'][-1]['kind']=='context' and value['trace'][-1]['status']=='bank_unavailable'
    assert len(calls)==2  # the LLM is not asked to fabricate substitute bank evidence
    assert not value['executed_operations'] and not any(r['node_id']=='action' for r in value['trace'])


@pytest.mark.parametrize('edited',[False,True])
def test_v2_migration_keeps_backup_and_custom_edits(private_config,edited):
    from intent_lab.workflow_templates import support_workflow_v2
    graph=support_workflow_v2()
    if edited:graph['nodes'][0]['label']['es']='Personalizado'
    record=editor.save_workflow(graph)
    (private_config/'master-workflow.json').write_text(json.dumps({'id':record['id'],'template_version':2}),encoding='utf-8')
    updated=editor.master_workflow()
    if edited: assert updated==record
    else:
        assert updated['revision']==2 and len(updated['graph']['nodes'])==24
        assert json.loads((private_config/'workflow-revisions'/f"{record['id']}-v1.json").read_text(encoding='utf-8'))==record
