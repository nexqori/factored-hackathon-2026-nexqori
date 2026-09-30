from uuid import uuid4
from backend.tests.test_api import setup, login
from backend.workflows import WORKFLOWS, workflow_view
from backend.catalog import SERVICES

def test_workflow_catalog_matches_server_requirements_and_languages():
    assert set(WORKFLOWS) <= set(SERVICES)
    for service_id, workflow in WORKFLOWS.items():
        assert set(workflow['steps'])=={'es','en','pt'}
        assert workflow['executesFinancialOperation'] is False
        assert workflow['creates']=='request'
        for locale in ('es','en','pt'):
            assert len(workflow_view(service_id,locale)['steps'])==4
            assert all(step.strip() for step in workflow['steps'][locale])

def test_contract_is_server_selected_persisted_and_retry_safe(setup):
    app,_=setup; client,_=login(app)
    for lang in ['es','en','pt']:
        contract=client.get('/api/services/unrecognized-charge?locale='+lang).json()['workflow']
        assert contract['id']=='unrecognized-charge' and 'transactionId' in contract['requiredFields']
    payload={'requestKey':str(uuid4()),'locale':'es','confirmed':True,'transactionId':'TX-1002','notes':'Verificación: no reconozco este movimiento.'}
    assert client.post('/api/services/unrecognized-charge/requests',json={**payload,'transactionId':None}).status_code==422
    assert client.post('/api/services/unrecognized-charge/requests',json={**payload,'transactionId':'TX-2001'}).status_code==404
    assert client.post('/api/services/unrecognized-charge/requests',json={**payload,'workflow':{'executesFinancialOperation':True}}).status_code==422
    created=client.post('/api/services/unrecognized-charge/requests',json=payload)
    assert created.status_code==201
    receipt=created.json()['id']; repeated=client.post('/api/services/unrecognized-charge/requests',json=payload)
    assert repeated.json()=={'id':receipt,'duplicate':True}
    case=next(c for c in client.get('/api/bootstrap').json()['requests'] if c['id']==receipt)
    assert case['serviceData']['workflow']=={'id':'unrecognized-charge','version':'2'}
    assert case['status']=='received'
