"""A runtime result and its messages/audits are one bank transaction."""
import copy

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend import workflow_chat as chat
from backend.db import make_sessions
from backend.models import AssistantTurn, AuditEvent, Conversation, ConversationFlow, Message
from backend.tests.test_api import setup, login
from backend.tests.test_workflow_chat import models, message


def stored(engine):
    with make_sessions(engine)() as db:
        return {
            'counts': {model.__tablename__: db.scalar(select(func.count()).select_from(model))
                       for model in (AssistantTurn, AuditEvent, Conversation, ConversationFlow, Message)},
            'flows': {row.conversation_id: copy.deepcopy(row.state) for row in db.scalars(select(ConversationFlow))},
        }


@pytest.mark.parametrize('continuing', [False, True])
@pytest.mark.parametrize('failure_at', ['response', 'commit'])
def test_failed_bank_turn_rolls_back_context_messages_audit_and_idempotency(setup, models, monkeypatch, continuing, failure_at):
    app, engine = setup
    client, _ = login(app)
    calls, _ = models
    if continuing:
        first = client.post('/api/assistant/flow', json=message(transactionId='TX-1002'))
        assert first.status_code == 200
        body = message(conversationId=first.json()['conversation']['id'], message='Esperaba 100 MXN')
    else:
        body = message(transactionId='TX-1002')
    before = stored(engine)
    original_view, original_commit = chat.flow_view, Session.commit

    def fail(*args, **kwargs):
        raise RuntimeError('test turn failure before commit')

    if failure_at == 'response':
        monkeypatch.setattr(chat, 'flow_view', fail)
    else:
        monkeypatch.setattr(Session, 'commit', fail)
    call_count = len(calls)
    with pytest.raises(RuntimeError, match='test turn failure before commit'):
        client.post('/api/assistant/flow', json=body)
    assert stored(engine) == before
    assert len(calls) == call_count + (1 if continuing else 3)

    monkeypatch.setattr(chat, 'flow_view', original_view)
    monkeypatch.setattr(Session, 'commit', original_commit)
    # An explicit retry may invoke the provider again because the preceding
    # transaction never committed. There is no automatic runtime retry.
    result = client.post('/api/assistant/flow', json=body)
    assert result.status_code == 200, result.text
    saved = stored(engine)
    assert saved['counts']['messages'] == before['counts']['messages'] + 2
    assert saved['counts']['assistant_turns'] == before['counts']['assistant_turns'] + 1
    if continuing:
        assert result.json()['flow']['canRegister']
        assert saved['counts']['conversations'] == before['counts']['conversations']
    else:
        assert saved['counts']['conversations'] == before['counts']['conversations'] + 1
    calls_after_commit = len(calls)
    assert client.post('/api/assistant/flow', json=body).json() == result.json()
    assert len(calls) == calls_after_commit and stored(engine) == saved
