"""Código central: 2 → 3 → 4 → 5. Una función por turno, estado sólo en servidor."""
import copy
import threading
import uuid
from dataclasses import asdict

from .contratos import Conversation, UserMessage, Trace, AgentError, require, now, encode, digest
from .config import load_contracts
from .proveedores import Providers
from .codigo2_tipo import detectar_tipo
from .codigo3_intencion import detectar_intencion
from .codigo4_evidencia import extraer_datos, merge_fields, clasificar_evidencia, preguntar
from .codigo5_rag import responder_rag
from .codigo7_humano import solicitar_atencion
from .mensajes import accion_pendiente, ERROR


class MemoryStore:
    """Almacén local de proceso. No es persistencia durable ni sesión de navegador."""
    def __init__(self):
        self.conversations = {}
        self.responses = {}
        self.lock = threading.RLock()


class ChatAgent:
    def __init__(self, settings, repository, store=None, provider_factory=Providers, contracts=None, document_handler=None, human_handler=None):
        self.document_handler, self.human_handler = document_handler, human_handler
        self.settings, self.repository = settings, repository
        self.store, self.provider_factory = store or MemoryStore(), provider_factory
        self.taxonomy, self.rules, self.versions = contracts or load_contracts()

    def _human(self, conversation, language, reason='rule'):
        return solicitar_atencion(conversation, self.human_handler, reason=reason) if self.human_handler else accion_pendiente('human', language)

    def _question(self, conversation, action, missing, providers, language, *, misunderstood=False):
        if misunderstood and conversation.question:
            conversation.misunderstood_replies += 1
        # Respuesta inicial no entendida + dos respuestas adicionales no entendidas = 3.
        if conversation.misunderstood_replies >= 3 or conversation.clarification_rounds >= self.settings.max_clarification_rounds:
            return self._human(conversation, language, 'clarification_limit')
        question = preguntar(conversation.model_context(), self.rules, action, missing, language,
                              providers, not_understood=misunderstood)
        conversation.question = question
        conversation.clarification_rounds += 1
        return {'status': 'awaiting_user', 'text': question, 'missing_fields': missing,
                'misunderstood_replies': conversation.misunderstood_replies,
                'additional_misunderstood_replies_before_human': max(0, 3-conversation.misunderstood_replies),
                'execution_authorized': False}

    def _flow(self, conversation, message, token, providers, trace):
        context = conversation.model_context()
        kind = detectar_tipo(context, providers)
        trace.add('codigo2.resultado', judgment=kind)
        if kind['label'] == 'reclamo':
            return accion_pendiente('complaint', message.language)
        if kind['label'] == 'desconocido':
            return self._question(conversation, None, ['objective'], providers, message.language, misunderstood=True)
        selected = detectar_intencion(context, self.taxonomy, self.rules, providers)
        intent, action = selected['intent']['label'], selected['selected_action']
        trace.add('codigo3.resultado', intent=selected['intent'], action=selected['action'])
        if intent == 'unknown' or action['kind'] == 'clarify':
            return self._question(conversation, action, ['objective'], providers, message.language, misunderstood=True)
        if (conversation.intent, conversation.action_id) != (intent, action['id']):
            conversation.fields.clear(); conversation.field_sources.clear()
        conversation.intent, conversation.action_id = intent, action['id']
        extracted = extraer_datos(conversation.model_context(), message.text, action, providers)
        if not extracted['understood']:
            return self._question(conversation, action, action['requires'], providers, message.language, misunderstood=True)
        merge_fields(conversation, extracted)
        trace.add('codigo4.campos', fields=conversation.fields, sources=conversation.field_sources)
        evidence = clasificar_evidencia(conversation.model_context(), action, self.rules, providers)
        conversation.cache['last_evidence'] = evidence['effective']
        trace.add('codigo4.resultado', evidence=evidence)
        if action['kind'] in {'navigate', 'unsupported'}:
            return accion_pendiente(action['kind'], message.language)
        if evidence['effective'] == 'desconocido':
            return self._question(conversation, action, ['objective'], providers, message.language, misunderstood=True)
        conversation.misunderstood_replies = 0
        if evidence['effective'] == 'insatisfecho':
            return self._question(conversation, action, evidence['missing'] or ['objective'], providers, message.language)
        if evidence['effective'] == 'humano' or action['kind'] == 'human':
            return self._human(conversation, message.language)
        if action['kind'] == 'document':
            if self.document_handler:
                return trace.call('codigo6.documento', self.document_handler, conversation, token, self.repository, trace)
            return accion_pendiente('document', message.language)
        if action['kind'] == 'supervised' or evidence['effective'] == 'supervisado':
            return accion_pendiente('supervised', message.language)
        response = trace.call('codigo5', responder_rag, conversation, intent, selected['rule'], action,
                              evidence, token, self.repository, providers, trace)
        if response['status'] == 'needs_selection':
            return self._question(conversation, action, ['selection'], providers, message.language)
        return response

    def handle_message(self, message: UserMessage | dict, *, session_token: str) -> dict:
        """Entrada para el futuro chatbot. No acepta historial/estado/identidad del modelo."""
        trace, conversation, authenticated = Trace(), None, False
        language, msg = 'es', None
        with self.store.lock:
            try:
                def parse_message():
                    candidate = UserMessage(**message) if isinstance(message, dict) else message
                    require(isinstance(candidate, UserMessage), 'INVALID_MESSAGE', 'Se requiere un mensaje estructurado.')
                    return candidate
                msg = trace.call('entrada.contrato', parse_message)
                trace.call('entrada.validar', msg.validate)
                language = msg.language
                trace.call('autorizacion', self.repository.authenticate, session_token, msg.user_id)
                authenticated = True
                fingerprint = digest(encode(asdict(msg)))
                cache_key = (msg.user_id, msg.message_id)
                previous = self.store.responses.get(cache_key)
                if previous:
                    require(previous['fingerprint'] == fingerprint, 'IDEMPOTENCY_CONFLICT', 'message_id reutilizado con otro contenido.')
                    return copy.deepcopy(previous['result'])
                if msg.conversation_id:
                    saved = self.store.conversations.get(msg.conversation_id)
                    require(saved is not None and saved.user_id == msg.user_id, 'CONVERSATION_ACCESS', 'Conversación inexistente o no accesible.')
                    conversation = copy.deepcopy(saved)
                else:
                    conversation = Conversation(str(uuid.uuid4()), msg.user_id)
                require(len(conversation.messages) < self.settings.max_messages, 'CONVERSATION_LIMIT', 'Iniciar otra conversación: límite alcanzado.')
                require(conversation.status != 'error', 'STOPPED_CONVERSATION', 'Conversación detenida por error; revisar causa e iniciar otra.')
                if conversation.status in {'answered', 'pending_implementation', 'document_ready', 'human_offer'}:
                    conversation.cache.clear()
                    conversation.fields.clear(); conversation.field_sources.clear()
                    conversation.question = None
                    conversation.misunderstood_replies = conversation.clarification_rounds = 0
                    conversation.intent = conversation.action_id = None
                conversation.messages.append({'id': str(uuid.uuid4()), 'client_message_id': msg.message_id,
                    'role': 'user', 'text': msg.text, 'language': language, 'timestamp': msg.timestamp,
                    'recorded_at': now(), 'channel': msg.channel, 'audio_ref': msg.audio_ref})
                providers = self.provider_factory(self.settings, trace)
                response = trace.call('orquestador.flujo', self._flow, conversation, msg, session_token, providers, trace)
            except Exception as exc:
                # Los errores fuera de un adaptador también quedan con origen rastreable.
                if not any(e.get('status') == 'error' for e in trace.events):
                    def raise_original():
                        raise exc
                    try:
                        trace.call('orquestador', raise_original)
                    except AgentError:
                        pass
                response = {'status': 'error', 'text': ERROR[language], 'execution_authorized': False}
                print(encode({'trace_id': trace.id, 'errors': [e for e in trace.events if e.get('status') == 'error']}))
            if conversation is not None:
                conversation.version += 1
                conversation.status = response['status']
                if response['status'] != 'awaiting_user':
                    conversation.question = None
                conversation.messages.append({'id': str(uuid.uuid4()), 'client_message_id': None, 'role': 'assistant',
                    'text': response['text'], 'language': language, 'timestamp': now(), 'recorded_at': now(),
                    'channel': 'text', 'audio_ref': None})
                self.store.conversations[conversation.id] = conversation
            result = {**response, 'conversation_id': conversation.id if conversation else None,
                'trace_id': trace.id, 'language': language, 'operations_executed': [],
                'execution_authorized': False, 'persistence': {
                    'schema_version': '1.0.0', 'turn_id': trace.id, 'user_id': msg.user_id if msg else None,
                    'authenticated': authenticated, 'client_message': asdict(msg) if msg else None,
                    'conversation': conversation.snapshot() if conversation else None,
                    'communication': {
                        'user_text': msg.text if msg else None, 'agent_text': response['text'],
                        'language': language, 'channel': msg.channel if msg else None,
                        'full_text': '\n'.join(m['role'] + ': ' + m['text'] for m in conversation.messages) if conversation else response['text']},
                    'response': copy.deepcopy(response), 'events': trace.events, 'contracts': self.versions,
                    'generated_at': now(), 'persisted': False}}
            if authenticated and msg is not None:
                self.store.responses[(msg.user_id, msg.message_id)] = {'fingerprint': fingerprint, 'result': copy.deepcopy(result)}
            return result


def solicitud_predeterminada(agent, *, user_id, session_token, text='¿Cuál es el saldo de todas mis cuentas?',
                             language='es', answers=()):
    """Ejemplo real opt-in. answers puede contener respuestas; no inventa respuestas faltantes."""
    result = agent.handle_message(UserMessage(user_id, text, language, now(), str(uuid.uuid4())), session_token=session_token)
    print(result['text'])
    for answer in answers:
        if result['status'] != 'awaiting_user':
            break
        result = agent.handle_message(UserMessage(user_id, answer, language, now(), str(uuid.uuid4()), result['conversation_id']), session_token=session_token)
        print(result['text'])
    return result
