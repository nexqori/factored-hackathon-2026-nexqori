from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from backend.catalog import SERVICES, search_services
from backend.db import make_sessions
from backend.models import Product, RequestCase, AuditEvent
from backend.navigation import navigate_in_app
from backend.tests.test_api import setup, login


@pytest.mark.parametrize('query,expected',[
    ('quiero pagar mi celular','phone-bill'),('pagar teléfono','phone-bill'),('Empresa Telefonica','phone-bill'),
    ('buscar pagar celular','phone-bill'),('donde puedo pagar celular','phone-bill'),
    ('pay my mobile phone bill','phone-bill'),('pagar minha fatura de celular','phone-bill'),
    ('pagar internet','internet-bill'),('Internet Plus','internet-bill'),('pagar televisão','tv-bill'),
    ('water bill','utilities-bill'),('cobro indebido','incorrect-charge'),('mortgage','mortgage'),
    ('problema con app','app-support'),('transferir dinero','bank-transfer')])
def test_search_matches_real_services(query,expected):
    assert search_services(query)[0]['id']==expected


def test_search_does_not_invent_providers_or_ignore_category():
    assert len(search_services('servicios'))==len(SERVICES)
    assert len(search_services('pagos'))==5
    assert search_services('Proveedor que no existe xyz')==[]
    assert search_services('celular',category='loans')==[]
    assert {s['provider'] for s in SERVICES.values() if s['kind']=='bill'}=={'Empresa Telefónica','Internet Plus','Cable TV','Servicios Públicos'}
    for item in SERVICES.values():
        assert set(item['copy'])=={'es','en','pt'}
        assert all(c['title'] and c['summary'] and c['keywords'] for c in item['copy'].values())


def test_catalog_requires_customer_and_localizes(setup):
    app,_=setup
    assert TestClient(app).get('/api/services').status_code==401
    admin,_=login(app,'nora'); assert admin.get('/api/services').status_code==403
    client,_=login(app)
    for locale,title in [('es','Pagar celular o teléfono'),('en','Pay a phone bill'),('pt','Pagar celular ou telefone')]:
        result=client.get('/api/services',params={'q':'celular','locale':locale}).json()
        assert result['total']==1 and result['items'][0]['title']==title
        assert result['items'][0]['provider']=='Empresa Telefónica'
    assert client.get('/api/services',params={'category':'admin'}).status_code==422
    assert client.get('/api/services/unknown-provider').status_code==404


def bill_payload(client,**overrides):
    account=next(p['id'] for p in client.get('/api/bootstrap').json()['products'] if p['type']=='account')
    return {'requestKey':str(uuid4()),'locale':'es','confirmed':True,'accountId':account,'reference':'5512345678','amountMinor':45990,'notes':'Verificación del catálogo',**overrides}


def test_specific_request_persists_without_debit_and_is_idempotent(setup):
    app,engine=setup; client,_=login(app)
    before=client.get('/api/bootstrap').json()['products']
    body={'requestKey':str(uuid4()),'locale':'es','confirmed':True,'notes':'Quiero conocer los requisitos del crédito.'}
    result=client.post('/api/services/personal-loan/requests',json=body)
    assert result.status_code==201,result.text
    assert client.post('/api/services/personal-loan/requests',json=body).json()=={'id':result.json()['id'],'duplicate':True}
    assert client.post('/api/services/personal-loan/requests',json={**body,'notes':'Quiero otros requisitos para el préstamo.'}).status_code==409
    assert client.post('/api/services/mortgage/requests',json=body).status_code==409
    after=client.get('/api/bootstrap').json()
    assert before==after['products']
    case=next(c for c in after['requests'] if c['id']==result.json()['id'])
    assert case['status']=='received' and case['catalogServiceId']=='personal-loan'
    assert case['serviceData']['amountMinor'] is None and case['serviceData']['reference']==''
    assert case['serviceData']['notes']==body['notes']
    other,_=login(app,'mateo')
    assert all(c['id']!=case['id'] for c in other.get('/api/bootstrap').json()['requests'])
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.request_id==case['id']))==1


@pytest.mark.parametrize('override',[
    {'confirmed':False},{'accountId':'account-01'},{'amountMinor':0},{'amountMinor':1.25},{'amountMinor':True},
    {'amountMinor':100000001},{'reference':'ab'},{'beneficiary':'Unexpected recipient'},
    {'transactionId':'TX-1002'},{'provider':'Invented company'}])
def test_inquiry_validation_is_server_side(setup,override):
    app,_=setup; client,_=login(app)
    body={'confirmed':True,'locale':'es','requestKey':str(uuid4()),'notes':'Consulta de requisitos del crédito',**override}
    assert client.post('/api/services/personal-loan/requests',json=body).status_code==422


@pytest.mark.parametrize('service,error',[
    ('phone-bill','use_bill_payment'),('internet-bill','use_bill_payment'),
    ('tv-bill','use_bill_payment'),('utilities-bill','use_bill_payment'),('bank-transfer','use_transfer')])
def test_money_operations_cannot_be_recorded_as_new_service_requests(setup,service,error):
    app,engine=setup; client,_=login(app)
    before=client.get('/api/bootstrap').json()
    response=client.post(f'/api/services/{service}/requests',json=bill_payload(client))
    assert response.status_code==409 and response.json()['error']==error
    after=client.get('/api/bootstrap').json()
    assert all(before[key]==after[key] for key in ('products','transactions','requests'))


def test_accounts_ownership_permissions_and_csrf(setup):
    app,engine=setup; client,_=login(app); other,_=login(app,'mateo'); admin,_=login(app,'nora')
    foreign=other.get('/api/bootstrap').json()['products'][0]['id']
    body={'confirmed':True,'locale':'es','requestKey':str(uuid4()),'notes':'Consulta de requisitos del crédito'}
    assert admin.post('/api/services/personal-loan/requests',json=body).status_code==403
    client.headers.pop('X-CSRF-Token')
    assert client.post('/api/services/personal-loan/requests',json=body).status_code==403
    with make_sessions(engine)() as db:
        own=db.scalar(select(Product).where(Product.id=='account-01'))
        db.add(RequestCase(id='invalid-owner-source',user_id=own.user_id,source_product_id=foreign,request_key=str(uuid4()),service='payments',reason='payment',details='Should fail at the database boundary'))
        with pytest.raises(IntegrityError): db.commit()


def test_claims_require_owned_transaction_and_inquiries_remain_requests(setup):
    app,_=setup; client,_=login(app); other,_=login(app,'mateo')
    payload={'requestKey':str(uuid4()),'locale':'pt','confirmed':True,'notes':'Consulta de verificação sobre o produto'}
    assert client.post('/api/services/unrecognized-charge/requests',json=payload).status_code==422
    foreign=other.get('/api/bootstrap').json()['transactions'][0]['id']
    assert client.post('/api/services/unrecognized-charge/requests',json={**payload,'transactionId':foreign}).status_code==404
    assert client.post('/api/services/personal-loan/requests',json=payload).status_code==201
    assert client.post('/api/services/account-balance/requests',json=payload).status_code==422


def test_agent_service_selection_only_navigates(setup):
    app,_=setup; client,_=login(app)
    count=len(client.get('/api/bootstrap').json()['requests'])
    for locale,message in [('es','quiero pagar celular'),('en','pay my phone bill'),('pt','pagar celular')]:
        result=client.post('/api/assistant',json={'message':message,'locale':locale}).json()
        assert result['navigation']==navigate_in_app('services','customer','phone-bill')
    assert len(client.get('/api/bootstrap').json()['requests'])==count
    for destination,service in [('services','../../admin'),('cards','phone-bill'),('services','unregistered')]:
        with pytest.raises(ValueError): navigate_in_app(destination,'customer',service)
