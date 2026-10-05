import pytest
from pydantic import ValidationError
from backend.assistant import answer
from backend.navigation import NavigateInput, navigate_in_app, ROUTES

@pytest.mark.parametrize('locale,messages', [
    ('es', ['Abre inicio','Ver productos','Ver movimientos','Mis solicitudes','Mis reclamos','Servicios','Ayuda','Mis cuentas','Tarjetas','Llévame a transferencias','Pagos','Préstamos','Inversiones','Seguros','Retiros','Configuración']),
    ('en', ['Open home','My products','Transactions','My requests','My complaints','Services','Help','Accounts','Cards','Transfer money','Bill payments','Loans','Investments','Insurance','Withdrawals','Settings']),
    ('pt', ['Abrir início','Meus produtos','Movimentações','Minhas solicitações','Minhas reclamações','Serviços','Ajuda','Contas','Cartões','Transferências','Pagamentos','Empréstimos','Investimentos','Seguros','Saques','Configurações']),
])
def test_all_destinations_in_three_languages(locale,messages):
    messages.insert(5,{'es':'Mis documentos','en':'My documents','pt':'Meus documentos'}[locale])
    for destination,message in zip(ROUTES,messages,strict=True):
        result=answer(message,locale,100)
        assert result['destination']==destination,(message,result)
        assert result['navigation']==navigate_in_app(destination,'customer')

def test_tool_rejects_arbitrary_routes_extra_fields_and_privileged_roles():
    for destination in ['admin','https://example.com','//example.com','javascript:alert(1)','../admin']:
        with pytest.raises(ValidationError): navigate_in_app(destination,'customer')
    with pytest.raises(ValidationError): NavigateInput(destination='home',role='admin')
    with pytest.raises(PermissionError): navigate_in_app('home','admin')

@pytest.mark.parametrize('message', ['Abre administración','Open admin','Abrir administração','No abras transferencias','Do not open transfers',"Don't open transfers",'Não abrir transferências','xyz123'])
def test_unsupported_or_negated_commands_do_not_navigate(message):
    assert answer(message,'es',100)['navigation'] is None

def test_context_and_request_preparation():
    assert answer('there','en',100,'cards')['navigation']['destination']=='cards'
    result=answer('No reconozco un movimiento','es',100)
    assert result['destination']=='new-request' and result['navigation'] is None

def test_filtered_navigation_is_structured_bounded_and_read_only():
    filters={'product':'account-01','start':'2026-09-01','end':'2026-09-30'}
    result=navigate_in_app('movements','customer',filters=filters)
    assert result['route']=='/movements?start=2026-09-01&end=2026-09-30&product=account-01'
    for invalid in ({'start':'2026-09-01'},{'start':'2026-02-30','end':'2026-03-01'},{'user':'someone'}, {'product':'../admin'},{}):
        with pytest.raises(ValueError):navigate_in_app('movements','customer',filters=invalid)
    with pytest.raises(ValueError):navigate_in_app('requests','customer',filters=filters)


def test_transaction_search_navigation_has_canonical_route_and_no_operation():
    assert navigate_in_app('movements','customer',filters={'transaction':'TX-123'})['route']=='/movements?transaction=TX-123'
    assert navigate_in_app('movements','customer',filters={'q':'Teléfono','status':'pending','amountMinor':45900})['route']=='/movements?q=Tel%C3%A9fono&status=pending&amountMinor=45900'
    for filters in ({'transaction':'../admin'},{'status':'refund'},{'amountMinor':True},{'amountMinor':-1},{'q':'a'*101}):
        with pytest.raises(ValueError):navigate_in_app('movements','customer',filters=filters)
