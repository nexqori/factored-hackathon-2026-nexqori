import json
import httpx
import pytest
from fastapi.testclient import TestClient
from test_providers import private_config, install_transport, response
from intent_lab import providers, dialogue, api

def envelope(value,**patch):
    return {'status':'completed','model':'gpt-6-luna','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}],'usage':{'input_tokens':100,'output_tokens':40},**patch}

def enable(path):
    with (path/'providers.env').open('a') as f:f.write('LLM_API_KEY=private-placeholder\nLLM_MODEL=gpt-6-luna\nLLM_REASONING_EFFORT=high\n')

def test_independent_classification_fixed_endpoint_and_no_secrets(private_config,monkeypatch):
    enable(private_config);calls=[]
    def handler(req):
        calls.append(req);payload=json.loads(req.content)
        if req.url.host=='api.typesafe.ai':return httpx.Response(200,json=response())
        assert str(req.url)=='https://api.openai.com/v1/responses'
        assert payload['model']=='gpt-6-luna' and payload['reasoning']=={'effort':'high'}
        assert payload['store'] is False and payload['text']['format']['strict'] is True
        context=json.loads(payload['input'][0]['content'])
        assert set(context)=={'criteria','language','messages'}
        return httpx.Response(200,json=envelope({'intent':'incorrect-charge','evidence_message_index':0,'needs_clarification':False}))
    install_transport(monkeypatch,handler)
    result=providers.classify([{'role':'user','content':'Cobro duplicado'}],'es','Classify')
    assert len(calls)==2 and result['llm']['status']=='ok'
    assert result['decision']['action'] is None
    assert 'private-placeholder' not in json.dumps(result)
    assert all('private-placeholder' not in p.read_text() for p in (private_config/'runs').glob('*.json'))

@pytest.mark.parametrize('raw,error',[
    (envelope({},status='incomplete'),'incomplete_response'),
    (envelope({},output=[{'type':'message','content':[{'type':'refusal','refusal':'private text'}]}]),'refusal'),
    (envelope({'intent':'not-a-service','evidence_message_index':0,'needs_clarification':False}),'invalid_response'),
    (envelope({'intent':'incorrect-charge','evidence_message_index':99,'needs_clarification':False}),'invalid_response'),
])
def test_rejects_incomplete_refused_or_invalid_outputs(private_config,monkeypatch,raw,error):
    enable(private_config)
    install_transport(monkeypatch,lambda req:httpx.Response(200,json=response() if req.url.host=='api.typesafe.ai' else raw))
    result=providers.classify([{'role':'user','content':'Hi'}],'en','Classify')
    assert result['llm']['error']==error and result['decision']['action'] is None

def test_dialogue_selects_contract_from_jev_and_records_provenance(private_config,monkeypatch):
    enable(private_config);dialogue.save_instructions('incorrect-charge','es','Pregunta por la fecha.')
    def handler(req):
        if req.url.host=='api.typesafe.ai':return httpx.Response(200,json=response())
        body=json.loads(req.content);context=json.loads(body['input'][0]['content'])
        assert context['contract']['id']=='incorrect-charge'
        assert context['contract']['custom_instructions']=='Pregunta por la fecha.'
        assert context['contract']['executes_operation'] is False and 'tools' not in body
        return httpx.Response(200,json=envelope({'reply':'¿Qué fecha aparece en el cargo?','next_step':'collect_context','missing_information':['fecha']}))
    install_transport(monkeypatch,handler)
    client=TestClient(api.app)
    result=client.post('/lab-api/dialogue',json={'language':'es','messages':[{'role':'user','content':'Me cobraron dos veces'}]}).json()
    assert result['llm']['status']=='ok' and result['executed_operations']==[]
    assert result['contract']['id']=='incorrect-charge'
    row=client.get('/lab-api/runs').json()['runs'][0]
    assert row['actor']=='local_operator' and row['kind']=='dialogue'
    detail=client.get('/lab-api/runs/'+row['id']).json()
    assert detail['result']['thread_id']==result['thread_id']
    assert client.post('/lab-api/dialogue',json={'messages':[{'role':'assistant','content':'Hi'}]}).status_code==422
    assert client.put('/lab-api/workflows/not-known',json={'language':'es','instructions':'test'}).status_code==404
    assert client.put('/lab-api/workflows/incorrect-charge',json={'language':'es','instructions':'test'},headers={'origin':'https://evil.invalid'}).status_code==403

def test_dialogue_does_not_call_llm_if_jev_fails(private_config,monkeypatch):
    enable(private_config);calls=[]
    def handler(req):calls.append(req);return httpx.Response(401,json={'error':'private-placeholder'})
    install_transport(monkeypatch,handler)
    result=dialogue.respond([{'role':'user','content':'Hi'}],'en','Classify')
    assert len(calls)==1 and result['contract'] is None
    assert result['llm']['error']=='classification_required' and result['executed_operations']==[]
