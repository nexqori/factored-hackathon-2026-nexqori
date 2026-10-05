import pytest
from sqlalchemy import select, func
from backend.chat_commands import application_command
from backend.tests.test_api import setup, login
from backend.tests.test_workflow_chat import models, message
from backend.tests.test_query_documents import query, body
from backend.models import AuditEvent
from backend.db import make_sessions
from backend.assistant import NAV_LABELS

COMMANDS = [
    ('Llévame a mis solicitudes','Show my requests','Me leve às minhas solicitações'),
    ('Abre mis reclamos','Open my complaints','Abra minhas reclamações'),
    ('Llévame al inicio','Go home','Vá ao início'),
    ('Abre centro de ayuda','Open the help center','Abra a central de ajuda'),
    ('Ver datos de mi tarjeta','Show my card details','Mostre os dados do meu cartão'),
    ('Bloquea mi tarjeta','Block my card','Bloqueie meu cartão'),
    ('Cierra sesión','Log me out','Encerre minha sessão'),
    ('Cambia mi fecha de nacimiento','Change my date of birth','Altere minha data de nascimento'),
    ('Cambia mi frecuencia bancaria','Change my banking frequency','Altere minha frequência bancária'),
    ('Cambia mi experiencia en banca digital','Change my digital banking experience','Altere minha experiência no banco digital'),
    ('Cambia cómo prefiero que me acompañen','Change my support preference','Altere minha preferência de ajuda'),
    ('Cambia el tamaño de letra a grande','Change my font size to large','Altere o tamanho da letra para grande'),
]


@pytest.mark.parametrize('phrases', COMMANDS)
@pytest.mark.parametrize('locale',['es','en','pt'])
def test_commands_respect_active_language(phrases,locale):
    for source,text in zip(('es','en','pt'),phrases):
        result=application_command(text,locale)
        assert result is not None, (text,locale)
        if source==locale:
            assert result.get('appCommand') or result.get('navigation'), (text,locale,result)
        else:
            assert not result.get('appCommand') and not result.get('navigation'), (text,locale,result)


@pytest.mark.parametrize('locale',['es','en','pt'])
def test_language_change_is_the_only_cross_language_command(locale):
    for text,target in [('Cambia el idioma a inglés','en'),('Switch to Portuguese','pt'),('Mude o idioma para espanhol','es')]:
        assert application_command(text,locale)['appCommand']=={'type':'set_locale','locale':target}


@pytest.mark.parametrize('locale',['es','en','pt'])
def test_every_allowed_screen_and_mixed_language(locale):
    for source,prefix in [('es','Llévame a '),('en','Open '),('pt','Abra ')]:
        for destination,label in NAV_LABELS[source].items():
            result=application_command(prefix+label,locale)
            assert result is not None,(source,destination,locale)
            assert result['destination']==(destination if source==locale else None),(source,destination,locale,result)
    mixed={'es':'Abre my cards','en':'Open mis tarjetas','pt':'Abra my cards'}[locale]
    assert application_command(mixed,locale)['navigation'] is None


@pytest.mark.parametrize('text,locale,field',[
    ('Cambia mi experiencia en banca digital','es','digitalExperience'),
    ('Change my digital banking experience','en','digitalExperience'),
    ('Altere minha experiência no banco digital','pt','digitalExperience'),
    ('Change my answer to how often I use banking services','en','bankingExperience'),
])
def test_profile_question_mapping_is_unambiguous(text,locale,field):
    assert application_command(text,locale)['appCommand']['field']==field


@pytest.mark.parametrize('locale,text',[
    ('es','Puedes cambiar mi fecha de nacimiento, por favor'),
    ('en','Could you change my date of birth, please'),
    ('pt','Você pode alterar minha data de nascimento, por favor'),
])
def test_profile_commands_with_polite_prefixes(locale,text):
    assert application_command(text,locale)['appCommand']['field']=='birthDate'


def test_short_logout_commands_cannot_cross_languages():
    assert application_command('Salir','es')['appCommand']['type']=='logout'
    assert application_command('Sair','pt')['appCommand']['type']=='logout'
    for locale in ('en','pt'): assert not application_command('Salir',locale).get('appCommand')
    for locale in ('en','es'): assert not application_command('Sair',locale).get('appCommand')


def test_guided_history_keeps_turn_order_when_clock_has_equal_timestamps(setup,monkeypatch):
    from datetime import datetime, timezone
    import backend.main as main
    app,_=setup;client,_=login(app)
    monkeypatch.setattr(main,'now',lambda:datetime(2026,10,4,tzinfo=timezone.utc))
    first=client.post('/api/assistant',json={'message':'Mi saldo','locale':'es'}).json()
    second=client.post('/api/assistant',json={'message':'Meu saldo','locale':'pt','conversationId':first['conversation']['id']}).json()
    history=client.get('/api/conversations/'+first['conversation']['id']).json()['messages']
    assert [m['id'] for m in history]==[m['id'] for m in first['messages']+second['messages']]


def test_profile_patch_confirms_validates_and_changes_only_one_field(setup):
    app,engine=setup;client,_=login(app);other,_=login(app,'mateo')
    form={'birthDate':'1987-02-14','bankingExperience':'frequent','digitalExperience':'confident','assistance':'auto'}
    assert client.patch('/api/profile/experience',json=form).status_code==200
    for field,value in [('birthDate','1990-12-31'),('bankingExperience','occasional'),('digitalExperience','learning'),('assistance','guided'),('textSize','large')]:
        before=client.get('/api/profile/experience').json()
        payload={'field':field,'value':value,'confirmed':True}
        assert client.patch('/api/profile/field',json={**payload,'confirmed':False}).status_code==422
        assert client.patch('/api/profile/field',json=payload,headers={'X-CSRF-Token':'bad'}).status_code==403
        assert client.get('/api/profile/experience').json()==before
        r=client.patch('/api/profile/field',json=payload);assert r.status_code==200,r.text
        if field=='textSize':assert r.json()['user']['textSize']==value
        elif field=='birthDate':assert client.get('/api/profile/experience').json()['birthDate']==value
        else:assert r.json()['user']['experience'][field]==value
    for field,value in [('birthDate','2030-01-01'),('birthDate','2000-02-30'),('assistance','admin'),('textSize','huge')]:
        assert client.patch('/api/profile/field',json={'field':field,'value':value,'confirmed':True}).status_code==422
    assert other.get('/api/profile/experience').json()=={'birthDate':'','experience':None}
    assert client.patch('/api/profile/field',json={'field':'textSize','value':'small','confirmed':True,'userId':'mateo'}).status_code==422
    admin,_=login(app,'nora');assert admin.patch('/api/profile/field',json=payload).status_code==403
    with make_sessions(engine)() as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action=='experience_updated'))==5


def test_pdf_closes_both_chat_routes_and_survives_reload(setup,models):
    app,_=setup;client,_=login(app);calls,control=models
    cid=query(client,control);payload=body()
    path='/api/conversations/'+cid+'/documents'
    made=client.post(path,json=payload);assert made.status_code==200
    assert client.post(path,json=payload).json()==made.json() # Lost response recovery.
    assert client.post(path,json=body()).json()['error']=='conversation_closed'
    assert client.get('/api/conversations/'+cid).json()['conversation']['closed'] is True
    before=len(calls)
    for endpoint in ['/api/assistant','/api/assistant/flow']:
        data=message(message='Llévame al inicio',conversationId=cid)
        if endpoint=='/api/assistant':data.pop('requestKey')
        r=client.post(endpoint,json=data);assert r.status_code==409 and r.json()['error']=='conversation_closed'
    assert len(calls)==before
    assert client.post('/api/assistant/flow',json=message(message='Llévame al inicio')).status_code==200


def test_foreign_queries_do_not_reach_models_or_advance_flow(setup,models):
    app,_=setup;client,_=login(app);calls,_=models
    before=len(calls)
    for text in ['Show my transactions','Quero pagar minha conta','Hello','Open my accounts']:
        r=client.post('/api/assistant/flow',json=message(message=text,locale='es'))
        assert r.status_code==200
        assert r.json()['flow'] is None and r.json()['navigation'] is None
    assert len(calls)==before


def test_connected_history_keeps_turn_order_with_frozen_clock(setup, models, monkeypatch):
    from datetime import datetime, timezone
    from backend import workflow_chat
    app, _ = setup
    client, _ = login(app)
    _, control = models
    monkeypatch.setattr(workflow_chat, 'now', lambda: datetime(2026, 10, 4, tzinfo=timezone.utc))
    cid = query(client, control)
    expected = client.get('/api/conversations/' + cid).json()['messages']
    for prompt in ['Llévame al inicio', 'Muéstrame los movimientos de todas mis cuentas']:
        response = client.post('/api/assistant/flow', json=message(message=prompt, conversationId=cid))
        assert response.status_code == 200, response.text
        expected += response.json()['messages']
    actual = client.get('/api/conversations/' + cid).json()['messages']
    assert [item['id'] for item in actual] == [item['id'] for item in expected]
