"""Pruebas escritas, NO ejecutadas. Sólo dobles locales, sin PostgreSQL ni APIs."""
import unittest
import uuid
from nexqori_chat.config import Settings
from nexqori_chat.contratos import UserMessage, now
from nexqori_chat.codigo1_orquestador import ChatAgent


class FakeRepository:
    def __init__(self):
        self.reads = 0

    def authenticate(self, token, expected_user):
        if token != 'fake-session' or expected_user != 'own-user':
            raise ValueError('Unauthorized test principal')
        return expected_user

    def retrieve(self, token, expected_user, intent, action, fields, trace):
        self.authenticate(token, expected_user)
        self.reads += 1
        return {'status': 'ok', 'facts': [{'fact_id': 'F1', 'source_ref': 'products:test', 'values': {'balance_display': '10.00 MXN'}}]}


class FakeProviders:
    calls = []

    def __init__(self, settings, trace):
        pass

    def choice(self, stage, state, instructions, criteria):
        self.calls.append(stage)
        if stage == 'codigo2.tipo':
            label = 'reclamo' if state['messages'][-1]['text'] == 'reclamo' else 'solicitud'
        elif stage == 'codigo3.intencion':
            text = state['messages'][-1]['text']
            label = {'documento': 'documents', 'persona': 'human'}.get(text, 'balance')
        elif stage == 'codigo3.accion':
            label = 'navigate' if state['conversation']['messages'][-1]['text'] == 'abrir' else 'read'
        else:
            label = 'automatico'
        return {'label': label, 'probability': 1.0, 'confidence': 1.0, 'probabilities': {label: 1.0}, 'model': 'fake'}

    def generate(self, stage, state, instructions, schema):
        self.calls.append(stage)
        if stage == 'codigo4.extraer':
            text = state['latest_text']
            return {'understood': text != '???', 'fields': [{'name': 'scope', 'value': 'all', 'quote': 'todas'}] if 'todas' in text else []}
        if stage == 'codigo4.preguntar':
            return {'question': 'No entendí la respuesta. ¿Una cuenta o todas?' if state['not_understood'] else '¿Una cuenta o todas?'}
        return {'answer': 'El saldo es 10.00 MXN [F1].', 'citations': ['F1'], 'operations_executed': False}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        FakeProviders.calls = []
        self.repo = FakeRepository()
        self.agent = ChatAgent(Settings(), self.repo, provider_factory=FakeProviders)

    def send(self, text, conversation_id=None, user='own-user', message_id=None):
        return self.agent.handle_message(UserMessage(user, text, 'es', now(), message_id or str(uuid.uuid4()), conversation_id), session_token='fake-session')

    def test_complaint_stops_before_intent_and_rag(self):
        result = self.send('reclamo')
        self.assertEqual(result['pending_kind'], 'complaint')
        self.assertEqual(FakeProviders.calls, ['codigo2.tipo'])
        self.assertEqual(self.repo.reads, 0)

    def test_missing_scope_then_answer(self):
        result = self.send('saldo')
        self.assertEqual(result['status'], 'awaiting_user')
        result = self.send('todas', result['conversation_id'])
        self.assertEqual(result['status'], 'answered')
        self.assertEqual(self.repo.reads, 1)
        self.assertEqual(len(result['persistence']['conversation']['messages']), 4)

    def test_three_ununderstood_replies_then_pending_human(self):
        result = self.send('saldo')
        for expected in (1, 2):
            result = self.send('???', result['conversation_id'])
            self.assertEqual(result['misunderstood_replies'], expected)
            self.assertEqual(result['status'], 'awaiting_user')
        result = self.send('???', result['conversation_id'])
        self.assertEqual(result['pending_kind'], 'human')
        self.assertEqual(self.repo.reads, 0)

    def test_pending_adapters_never_retrieve(self):
        for text, kind in [('abrir', 'navigate'), ('persona', 'human')]:
            result = self.send(text)
            self.assertEqual(result['pending_kind'], kind)
        self.assertEqual(self.repo.reads, 0)

    def test_document_without_minimum_fields_asks_instead_of_exporting(self):
        self.assertEqual(self.send('documento')['status'], 'awaiting_user')
        self.assertEqual(self.repo.reads, 0)

    def test_replay_does_not_call_models_twice(self):
        msg = UserMessage('own-user', 'todas', 'es', now(), str(uuid.uuid4()))
        first = self.agent.handle_message(msg, session_token='fake-session')
        count = len(FakeProviders.calls)
        second = self.agent.handle_message(msg, session_token='fake-session')
        self.assertEqual(first, second)
        self.assertEqual(len(FakeProviders.calls), count)

    def test_invalid_session_stops_before_models(self):
        result = self.send('saldo', user='other-user')
        self.assertEqual(result['status'], 'error')
        self.assertEqual(FakeProviders.calls, [])
        self.assertFalse(result['persistence']['authenticated'])


if __name__ == '__main__':
    unittest.main()
