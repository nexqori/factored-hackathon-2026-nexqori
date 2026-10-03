"""Multi-turn acceptance with the real interpreter and offline providers."""
import copy
import json
import re

import pytest
from sqlalchemy import select

from backend import workflow_chat as chat
from backend.conversation_context import changes_topic, provider_history
from backend.db import make_sessions
from backend.models import ConversationFlow, Message
from backend.tests.test_api import setup, login
from backend.tests.test_workflow_chat import models, message


def send(client, text, conversation=None, locale='es', **kwargs):
    response = client.post('/api/assistant/flow', json=message(
        message=text, locale=locale, **({'conversationId': conversation} if conversation else {}), **kwargs))
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('locale,opening,expected,correction', [
    ('es', 'Hay un importe incorrecto en este cobro', 'Esperaba 100 MXN', 'Me equivoqué: esperaba 120 MXN'),
    ('en', 'The amount of this charge is wrong', 'I expected 100 MXN', 'I made a mistake: I expected 120 MXN'),
    ('pt', 'O valor desta cobrança está incorreto', 'Esperava 100 MXN', 'Eu me enganei: esperava 120 MXN'),
])
def test_problem_clarification_after_review_reuses_contract_and_latest_correction(
        setup, models, monkeypatch, locale, opening, expected, correction):
    app, engine = setup
    client, _ = login(app)
    calls, control = models

    def extract(messages, language, fields, *args, **kwargs):
        calls.append(('llm', copy.deepcopy(messages)))
        found = []
        for index, entry in enumerate(messages):
            if entry['role'] == 'user' and (amount := re.search(r'\b(?:100|120) MXN\b', entry['content'])):
                found = [{'field': 'difference', 'value': amount[0], 'quote': amount[0], 'message_index': index}]
        return {'status': 'ok', 'observations': found, 'assessment': 'continue', 'latency_ms': 1}

    monkeypatch.setattr(chat.editor, 'extract', extract)
    before = client.get('/api/bootstrap').json()
    first = send(client, opening, locale=locale, transactionId='TX-1002')
    cid = first['conversation']['id']
    second = send(client, expected, cid, locale)
    assert second['flow']['canRegister']
    # The next turn is a correction to the same case, not a new classification.
    control.update(family='query', intent='account-balance')
    third = send(client, correction, cid, locale)
    assert third['flow']['canRegister']
    assert third['flow']['jev']['intent'] == 'incorrect-charge'
    assert third['flow']['contract'] == second['flow']['contract']
    assert [entry[0] for entry in calls] == ['triage', 'jev', 'llm', 'llm', 'llm']
    assert [entry['content'] for entry in calls[-1][1] if entry['role'] == 'user'] == [opening, expected, correction]
    with make_sessions(engine)() as db:
        row = db.get(ConversationFlow, cid)
        assert row.state['context']['observations'][0]['value'] == '120 MXN'
        assert row.state['conversation_context']['mode'] == 'continue_review'
        assert len(db.scalars(select(Message).where(Message.conversation_id == cid)).all()) == 6
    assert 'Stream Plus' not in json.dumps(calls) and '2026-09-27' not in json.dumps(calls)
    assert client.get('/api/conversations/' + cid + '/flow').json()['flow'] == third['flow']
    after = client.get('/api/bootstrap').json()
    for key in ('products', 'transactions', 'requests'):
        assert after[key] == before[key]


@pytest.mark.parametrize('locale,transition', [
    ('es', 'Ahora quiero saber mi saldo'),
    ('en', 'Now I want to check my balance'),
    ('pt', 'Agora quero consultar meu saldo'),
])
def test_explicit_new_topic_interrupts_pending_question_but_keeps_safe_history(setup, models, locale, transition):
    app, engine = setup
    client, _ = login(app)
    calls, control = models
    first = send(client, 'Quiero revisar un cobro incorrecto', locale=locale, transactionId='TX-1002')
    assert first['flow']['execution']['phase'] == 'waiting_reply'
    cid = first['conversation']['id']
    control.update(family='query', intent='account-balance')
    second = send(client, transition, cid, locale)
    assert second['flow']['triage']['family'] == 'query'
    assert second['flow']['jev']['intent'] == 'account-balance'
    assert second['flow']['contract'] is None and not second['flow']['canRegister']
    assert 'MXN' in second['text']
    control['intent'] = 'documents'
    third = send(client, {'es': '¿Y puedo tenerlo en PDF?', 'en': 'Can I have that as a PDF?', 'pt': 'Posso ter isso em PDF?'}[locale], cid, locale)
    assert third['flow']['canDocument']
    assert [entry[0] for entry in calls] == ['triage', 'jev', 'llm', 'triage', 'jev', 'triage', 'jev']
    assert calls[-1][1][0]['content'] == 'Quiero revisar un cobro incorrecto'
    assert second['text'] not in [entry['content'] for entry in calls[-1][1]]
    assert chat.SERVICES['account-balance']['copy'][locale]['title'] in calls[-1][1][-2]['content']
    with make_sessions(engine)() as db:
        assert db.get(ConversationFlow, cid).state['conversation_context']['mode'] == 'classify'


def test_three_queries_keep_actual_topic_without_bank_records_in_model_history(setup, models):
    app, _ = setup
    client, _ = login(app)
    calls, control = models
    control.update(family='query', intent='account-balance')
    first = send(client, '¿Cuál es mi saldo?')
    cid = first['conversation']['id']
    control['intent'] = 'account-activity'
    second = send(client, 'Muéstrame los movimientos de todas mis cuentas', cid)
    assert 'TX-1002' in second['text']
    control['intent'] = 'documents'
    third = send(client, 'Y quiero un documento de eso', cid)
    assert third['flow']['canDocument'] and 'PDF' in third['text']
    transcript = calls[-1][1]
    assert [entry['content'] for entry in transcript if entry['role'] == 'user'] == [
        '¿Cuál es mi saldo?', 'Muéstrame los movimientos de todas mis cuentas', 'Y quiero un documento de eso']
    assert chat.SERVICES['account-balance']['copy']['es']['title'] in transcript[1]['content']
    assert chat.SERVICES['account-activity']['copy']['es']['title'] in transcript[3]['content']
    provider_text = json.dumps(calls, ensure_ascii=False)
    assert 'Stream Plus' not in provider_text and 'TX-1002' not in provider_text
    assert first['text'] not in provider_text and second['text'] not in provider_text


def test_suggestion_confirmation_is_explained_in_safe_history_before_next_clarification(setup, models):
    app, _ = setup
    client, _ = login(app)
    calls, _ = models
    first = send(client, 'Quiero revisar un cobro incorrecto')
    cid = first['conversation']['id']
    assert first['flow']['suggestedTransaction'] is not None
    second = send(client, 'Sí, es este', cid)
    assert second['flow']['missing_fields'] == ['difference']
    third = send(client, 'Esperaba 100 MXN', cid)
    assert third['flow']['canRegister']
    assert 'movimiento que te propuse' in calls[-1][1][1]['content']
    assert first['flow']['suggestedTransaction']['id'] not in json.dumps(calls)
    assert first['flow']['suggestedTransaction']['merchant'] not in json.dumps(calls)
    assert [entry[0] for entry in calls] == ['triage', 'jev', 'llm', 'llm', 'llm']


def test_context_provider_failure_does_not_erase_the_selected_contract_or_user_answer(setup, models, monkeypatch):
    app, _ = setup
    client, _ = login(app)
    calls, control = models
    original = chat.editor.extract
    available = {'ok': True}

    def extract(messages, *args, **kwargs):
        if not available['ok']:
            calls.append(('llm', copy.deepcopy(messages)))
            return {'status': 'error', 'error': 'timeout', 'latency_ms': 1}
        answer = original(messages, *args, **kwargs)
        match = next((i for i, entry in enumerate(messages)
                      if entry['role'] == 'user' and '100 MXN' in entry['content']), None)
        if match is not None:
            answer['observations'] = [{'field': 'difference', 'value': '100 MXN', 'quote': '100 MXN', 'message_index': match}]
        return answer

    monkeypatch.setattr(chat.editor, 'extract', extract)
    first = send(client, 'Hay un importe incorrecto', transactionId='TX-1002')
    cid = first['conversation']['id']
    available['ok'] = False
    second = send(client, 'Esperaba 100 MXN', cid)
    assert second['flow']['state'] == 'provider_unavailable'
    available['ok'] = True
    control['intent'] = 'needs-clarification'
    third = send(client, 'Inténtalo otra vez con lo que te indiqué', cid)
    assert third['flow']['canRegister']
    assert third['flow']['jev']['intent'] == 'incorrect-charge'
    assert [entry[0] for entry in calls] == ['triage', 'jev', 'llm', 'llm', 'llm']
    assert any(entry['content'] == 'Esperaba 100 MXN' for entry in calls[-1][1])


@pytest.mark.parametrize('text', [
    'Esperaba 100 MXN', 'Ahora recuerdo: ocurrió el martes', 'Sí, es este',
    'No, ahora quiero agregar que falló dos veces', 'El mensaje dice "otra consulta"',
    'I expected 100 MXN', 'Now I remember the date', 'Sim, é esse', 'Agora lembro a data',
])
def test_clarifications_do_not_change_the_topic(text):
    assert not changes_topic(text)


def test_bounded_provider_context_retains_opening_story_and_recent_correction():
    messages = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': str(i)} for i in range(36)]
    value = provider_history({'messages': messages})
    assert len(value) == 28
    assert value[:2] == messages[:2] and value[-2:] == messages[-2:]
    assert value[2:] == messages[-26:]
    value[0]['content'] = 'changed'
    assert messages[0]['content'] == '0'
