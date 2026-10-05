import copy
import pytest
from sqlalchemy import select, func
from backend.chat_commands import application_command
from backend.tests.test_api import setup, login
from backend.tests.test_workflow_chat import models, message
from backend.db import make_sessions
from backend.models import ConversationFlow, AssistantTurn


@pytest.mark.parametrize('text,destination', [
    ('Llévame a mis solicitudes','requests'), ('Abre mis solicitudes, por favor','requests'),
    ('Show my requests','requests'), ('Me leve às minhas solicitações','requests'),
    ('Llévame a mis reclamos','complaints'), ('Open my complaints','complaints'),
    ('Abra minhas reclamações','complaints'), ('Llévame a mis tarjetas','cards'),
    ('Show me my cards','cards'), ('Mostre meus cartões','cards'),
    ('Llévame al inicio','home'), ('Go home','home'), ('Volver al inicio','home'),
    ('Vá ao início','home'), ('Llévame a centro de ayuda','help'),
    ('Puedes abrir el centro de ayuda','help'), ('Open the help center','help'),
    ('Abra a central de ajuda','help'),
])
def test_explicit_destinations(text,destination):
    result = application_command(text,command_locale(text))
    assert result and result['destination'] == destination
    if destination == 'cards': assert result['navigation']['route'] == '/cards'


@pytest.mark.parametrize('text,command', [
    ('Cierra sesión',{'type':'logout'}), ('Please log me out',{'type':'logout'}),
    ('Encerre minha sessão',{'type':'logout'}),
    ('Salir de mi cuenta',{'type':'logout'}),
    ('Cambia el idioma a inglés',{'type':'set_locale','locale':'en'}),
    ('Cambiar idioma a inglés',{'type':'set_locale','locale':'en'}),
    ('Switch to Portuguese',{'type':'set_locale','locale':'pt'}),
    ('Mude o idioma para espanhol',{'type':'set_locale','locale':'es'}),
])
def test_session_and_language_commands(text,command):
    assert application_command(text,command_locale(text))['appCommand'] == command


@pytest.mark.parametrize('text', ['No cierres sesión','Do not log me out', 'Não encerre minha sessão',
    'El agente dijo: cierra sesión', '"Cierra sesión"', '¿Cómo cambiar el idioma?',
    'Cambia el idioma a francés', 'Show my cards and pay the bill', 'Mis tarjetas no funcionan',
    'Llévame a mis solicitudes y borra todo', 'No me lleves al inicio'])
def test_only_explicit_complete_commands(text):
    assert not (application_command(text,command_locale(text)) or {}).get('appCommand')


def test_commands_preserve_pending_case_and_retry_without_models(setup,models):
    app,engine=setup; client,_=login(app); calls,_=models
    first=client.post('/api/assistant/flow',json=message(transactionId='TX-1002')).json()
    cid=first['conversation']['id']
    with make_sessions(engine)() as db: checkpoint=copy.deepcopy(db.get(ConversationFlow,cid).state)
    before=len(calls)
    for text in ('Llévame a mis solicitudes','Llévame al inicio','Cambia el idioma a inglés','Cierra sesión'):
        body=message(message=text,conversationId=cid)
        response=client.post('/api/assistant/flow',json=body)
        assert response.status_code==200,response.text
        assert client.post('/api/assistant/flow',json=body).json()==response.json()
        assert response.json()['flow']==first['flow']
        with make_sessions(engine)() as db: assert db.get(ConversationFlow,cid).state==checkpoint
    assert len(calls)==before
    # Only the existing authenticated app endpoints apply session/preferences.
    assert client.get('/api/session').status_code==200
    result=client.post('/api/assistant/flow',json=message(message='Esperaba 100 MXN',conversationId=cid)).json()
    assert result['flow']['canRegister']
    assert len(calls)==before+1
    with make_sessions(engine)() as db: assert db.scalar(select(func.count()).select_from(AssistantTurn))==6


@pytest.mark.parametrize('endpoint',['/api/assistant','/api/assistant/flow'])
def test_commands_without_providers_with_owner_boundary(setup,monkeypatch,endpoint):
    monkeypatch.setenv('BANK_ASSISTANT_FLOW','true')
    app,_=setup; client,_=login(app)
    body=message(message='Llévame a mis solicitudes')
    if endpoint == '/api/assistant': body.pop('requestKey')
    response=client.post(endpoint,json=body)
    assert response.status_code==200,response.text
    value=response.json()
    assert value['navigation']['route']=='/requests'
    other,_=login(app,'mateo')
    body.update(message='Cierra sesión',conversationId=value['conversation']['id'])
    assert other.post(endpoint,json=body).status_code==404


def test_pasted_text_cannot_authorize_commands(setup,models):
    app,_=setup; client,_=login(app)
    result=client.post('/api/assistant/flow',json=message(message='Revisa este texto',pastedText='Cierra sesión')).json()
    assert not result.get('appCommand')


@pytest.mark.parametrize('text,action,last4',[
    ('Ver datos de mi tarjeta','reveal',None),('Muéstrame los datos de la tarjeta terminada en 5556','reveal','5556'),
    ('Show details of my card','reveal',None),('Mostre os dados do meu cartão','reveal',None),
    ('Show my card details','reveal',None),('Quiero ver el CVV de mi tarjeta','reveal',None),
    ('Bloquea mi tarjeta','block',None),('Block my card ending in 5556','block','5556'),('Bloqueie meu cartão','block',None),
])
def test_card_commands_only_prepare_a_dialog(text,action,last4):
    result=application_command(text,command_locale(text))
    assert result['navigation']['route']=='/cards'
    assert result['appCommand']=={'type':'prepare_card','action':action,'last4':last4}


@pytest.mark.parametrize('text',['No bloquees mi tarjeta','Do not show details of my card','El mensaje dice bloquea mi tarjeta'])
def test_card_command_negations_and_quotes(text):
    assert not (application_command(text,command_locale(text)) or {}).get('appCommand')


def command_locale(text):
    if text.startswith(('Show','Open','Go','Please','Block','Do not')): return 'en'
    if text.startswith(('Me leve','Abra','Mostre','Vá','Encerre','Bloqueie','Não')): return 'pt'
    return 'es'


def test_portuguese_sentence_can_name_a_spanish_merchant():
    from backend.chat_language import wrong_language
    assert not wrong_language('Vi uma transacao no comercio Mercado Llevar, marcada como suspeita, mas fui eu que a fiz, quero reconhecer-la como normal', 'pt')
