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
