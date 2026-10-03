import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.agent_routing import PROBLEMS, SERVICES, TOOLS, route_plan, tools_for
from backend.db import make_sessions
from backend.models import AuditEvent
from backend.tests.test_api import setup, login, ORIGIN
from backend.tests.test_operations import make_refund

ENDPOINT = '/api/assistant/tools/read'


def call(client, intent, tool, **extra):
    return client.post(ENDPOINT, json={'intent': intent, 'tool': tool, **extra})


def test_routes_use_known_tools_and_queries_never_prepare_problem_actions():
    for intent in SERVICES.keys() | {'request-status'}:
        plan = route_plan({'status': 'ok', 'intent': intent})
        assert plan['status'] == 'proposed' and plan['authorizes_execution'] is False
        assert plan['executed_tools'] == plan['executed_operations'] == []
        assert all(t['id'] in TOOLS and set(t['titles']) == {'es','en','pt'} for t in plan['tools'])
        if plan['family'] == 'query':
            assert plan['contract'] is None and all(t['kind'] == 'read' for t in plan['tools'])
        if intent in PROBLEMS:
            assert plan['contract']['id'] == intent
    for candidate in ({'status':'error','intent':'incorrect-charge'}, {'status':'ok','intent':'administrator'}, {'status':'ok','intent':[]}):
        plan = route_plan(candidate)
        assert plan['status'] == 'unavailable' and plan['tools'] == []
    for intent in ('needs-clarification','multiple-intents','out-of-scope'):
        assert route_plan({'status':'ok','intent':intent})['tools'] == []
    assert 'prepare-card-block' in tools_for('unrecognized-charge')
    assert 'prepare-card-block' not in tools_for('incorrect-charge')
    assert all(t['kind'] == 'read' for t in route_plan({'status':'ok','intent':'request-status'})['tools'])


def test_gateway_is_read_only_owned_bounded_and_audited(setup):
    app, engine = setup
    customer, _ = login(app)
    other, _ = login(app, 'mateo')
    case, _, refund = make_refund(customer)
    before = customer.get('/api/bootstrap').json()
    for client in (customer, other):
        own = client.get('/api/bootstrap').json()
        balances = call(client, 'account-balance','read-balances').json()
        assert balances['status'] == 'executed' and balances['executed_operations'] == []
        assert {r['id'] for r in balances['data']['products']} <= {r['id'] for r in own['products']}
        txs = call(client,'account-activity','read-transactions').json()['data']
        assert txs['limit'] == 20
        assert {r['id'] for r in txs['transactions']} <= {r['id'] for r in own['transactions']}
    cards = call(customer,'my-cards','read-cards').json()['data']['cards']
    assert cards and all(set(card) == {'id','last4','status'} for card in cards)
    result = call(customer,'request-status','read-request-status',referenceId=case)
    assert result.status_code == 200
    assert result.json()['data']['refund']['id'] == refund['id']
    evidence = call(customer,'incorrect-charge','read-transaction-evidence',referenceId='TX-1001').json()
    assert evidence['data']['externalProcessorLogs'] is False
    assert evidence['data']['transaction']['id'] == 'TX-1001'
    with make_sessions(engine)() as db:
        event = db.get(AuditEvent, evidence['auditEventId'])
        assert event.user_id == event.actor_id == 'andrea'
        assert event.transaction_id == 'TX-1001' and event.request_id == case
        assert event.action == 'tool_transaction_evidence'
    after = customer.get('/api/bootstrap').json()
    assert [before[k] for k in ('products','transactions','requests')] == [after[k] for k in ('products','transactions','requests')]


@pytest.mark.parametrize('locale', ['es','en','pt'])
def test_static_information_and_problem_contract_are_separate(setup, locale):
    app, _ = setup
    client, _ = login(app)
    info = call(client,'personal-loan','read-service-info',locale=locale)
    assert info.status_code == 200
    assert info.json()['data']['service']['workflow'] is None
    contract = call(client,'app-support','read-problem-contract',locale=locale)
    assert contract.status_code == 200
    assert contract.json()['data']['contract']['id'] == 'app-support'
    assert call(client,'personal-loan','read-problem-contract',locale=locale).status_code == 403
    assert call(client,'account-balance','read-transaction-evidence',referenceId='TX-1001').status_code == 403
    assert call(client,'phone-bill','read-service-info',locale=locale).status_code == 200


def test_gateway_rejects_cross_owner_forgery_and_financial_tools(setup):
    app, engine = setup
    customer, _ = login(app)
    other, _ = login(app,'mateo')
    admin, _ = login(app,'nora')
    case, _, _ = make_refund(customer)
    cid = customer.post('/api/assistant',json={'message':'Verificación de contexto.','locale':'es','currentPage':'movements','transactionId':'TX-1001'}).json()['conversation']['id']
    assert call(customer,'incorrect-charge','read-transaction-evidence',referenceId='TX-1001',conversationId=cid).status_code == 200
    with make_sessions(engine)() as db:
        events = db.scalars(select(AuditEvent).where(AuditEvent.action.like('tool_%'))).all()
        assert len(events) == 1 and events[0].conversation_id == cid
    for client in (other,):
        assert call(client,'incorrect-charge','read-transaction-evidence',referenceId='TX-1001').status_code == 404
        assert call(client,'request-status','read-request-status',referenceId=case).status_code == 404
        assert call(client,'account-balance','read-balances',conversationId=cid).status_code == 404
    assert call(customer,'incorrect-charge','read-transaction-evidence',referenceId='TX-1002',conversationId=cid).status_code == 409
    assert call(admin,'account-balance','read-balances').status_code == 403
    assert TestClient(app).post(ENDPOINT,json={'intent':'account-balance','tool':'read-balances'},headers={'Origin':ORIGIN}).status_code == 401
    assert call(customer,'request-status','read-request-status').status_code == 422
    assert call(customer,'account-balance','read-balances',referenceId='andrea').status_code == 422
    for extra in ({'userId':'mateo'}, {'role':'admin'}, {'confirmed':True}, {'sql':'SELECT * FROM users'}):
        assert call(customer,'account-balance','read-balances',**extra).status_code == 422
    for tool in ('prepare-card-block','prepare-refund-review','prepare-request','execute-sql','approve-refund'):
        assert call(customer,'unrecognized-charge',tool).status_code == 403
    assert call(customer,'unknown','read-balances').status_code == 403
    assert customer.post(ENDPOINT,json={'intent':'account-balance','tool':'read-balances'},headers={'X-CSRF-Token':'wrong'}).status_code == 403
    assert customer.post(ENDPOINT,json={'intent':'account-balance','tool':'read-balances'},headers={'Origin':'http://localhost:5190'}).status_code == 403
