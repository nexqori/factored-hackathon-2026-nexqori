"""Artefactos y atención interna temporales. No escribe ninguna tabla."""
import copy
import threading
import time
from uuid import uuid4
from fastapi import HTTPException
from .models import User
from .security import digest
from nexqori_chat.codigo6_documentos import recuperar_documento, generar_pdf
from nexqori_chat.contratos import now

COPY = {
 'es': {'document': 'Tu PDF está listo para descargar. Contiene información de consulta, no una certificación oficial.',
        'human': 'Puedo compartir esta conversación con un agente del panel de Nexqori. Revisa el contexto y confirma el envío; todavía no se ha compartido.'},
 'en': {'document': 'Your PDF is ready to download. It contains reference information, not an official certificate.',
        'human': 'I can share this conversation with an agent in the Nexqori panel. Review the context and confirm; it has not been shared yet.'},
 'pt': {'document': 'Seu PDF está pronto para baixar. Contém informações de consulta, não uma certificação oficial.',
        'human': 'Posso compartilhar esta conversa com um agente no painel Nexqori. Revise o contexto e confirme o envio; ainda não foi compartilhado.'}}


class ChatActions:
    def __init__(self, gateway):
        self.gateway = gateway
        self.lock = threading.RLock()
        self.documents, self.tickets = {}, {}

    def _purge(self):
        current = time.monotonic()
        self.documents = {k: v for k, v in self.documents.items() if v['expires'] > current}
        self.tickets = {k: v for k, v in self.tickets.items() if v['expires'] > current}

    def forget(self, token):
        with self.lock:
            key = digest(token)
            self.documents = {k: v for k, v in self.documents.items() if v['session'] != key}
            self.tickets = {k: v for k, v in self.tickets.items() if v['session'] != key}

    def _name(self, user_id):
        with self.gateway.sessions() as db:
            return db.get(User, user_id).name

    def document(self, conversation, token, repository, trace):
        self.gateway.authorize(token, conversation.user_id)
        packet = recuperar_documento(conversation, token, repository, trace)
        content = generar_pdf(packet, customer_name=self._name(conversation.user_id), language=conversation.messages[-1]['language'])
        self.gateway.authorize(token, conversation.user_id)
        with self.lock:
            self._purge()
            if len(self.documents) >= 100 or len(content) > 2_000_000:
                raise HTTPException(429, 'chat_limit')
            doc_id = str(uuid4())
            self.documents[doc_id] = {'session': digest(token), 'user_id': conversation.user_id,
                'content': content, 'expires': time.monotonic() + 900, 'filename': f'nexqori-{packet["type"]}.pdf'}
        return {'status': 'document_ready', 'text': COPY[conversation.messages[-1]['language']]['document'],
            'document': {'id': doc_id, 'filename': self.documents[doc_id]['filename']}, 'execution_authorized': False}

    def download(self, doc_id, token, user_id):
        self.gateway.authorize(token, user_id)
        with self.lock:
            self._purge()
            record = self.documents.get(doc_id)
            if not record or record['session'] != digest(token) or record['user_id'] != user_id:
                raise HTTPException(404, 'not_found')
            return record['content'], record['filename']

    def offer(self, conversation, context, token):
        self.gateway.authorize(token, conversation.user_id)
        with self.lock:
            self._purge()
            if len(self.tickets) >= 100:
                raise HTTPException(429, 'chat_limit')
            ticket_id = str(uuid4())
            self.tickets[ticket_id] = {'id': ticket_id, 'session': digest(token), 'user_id': conversation.user_id,
                'customerName': self._name(conversation.user_id), 'context': copy.deepcopy(context),
                'status': 'draft', 'messages': [], 'assignedTo': None, 'createdAt': now(),
                'expires': time.monotonic() + 7200}
        return {'status': 'human_offer', 'text': COPY[context['language']]['human'],
            'handoff': {'id': ticket_id}, 'execution_authorized': False}

    @staticmethod
    def _public(record):
        return copy.deepcopy({k: record[k] for k in ('id', 'customerName', 'context', 'status', 'messages', 'assignedTo', 'createdAt')})

    def _owned(self, ticket_id, token, user_id):
        self.gateway.authorize(token, user_id)
        self._purge()
        ticket = self.tickets.get(ticket_id)
        if not ticket or ticket['session'] != digest(token) or ticket['user_id'] != user_id:
            raise HTTPException(404, 'not_found')
        return ticket

    def customer_list(self, token, user_id):
        self.gateway.authorize(token, user_id)
        with self.lock:
            self._purge()
            return [self._public(t) for t in self.tickets.values() if t['session'] == digest(token) and t['user_id'] == user_id]

    def confirm(self, ticket_id, token, user_id):
        with self.lock:
            ticket = self._owned(ticket_id, token, user_id)
            if ticket['status'] == 'draft':
                ticket['status'] = 'queued'
                ticket['confirmedAt'] = now()
            return self._public(ticket)

    def admin_list(self):
        # La ruta HTTP exige admin; los borradores nunca se comparten.
        with self.lock:
            self._purge()
            return [self._public(t) for t in self.tickets.values() if t['status'] != 'draft']

    def post_message(self, ticket_id, payload, *, token=None, user_id=None, operator=None):
        with self.lock:
            self._purge()
            ticket = self.tickets.get(ticket_id) if operator else self._owned(ticket_id, token, user_id)
            if not ticket or ticket['status'] == 'draft':
                raise HTTPException(404, 'not_found')
            if ticket['status'] == 'closed':
                raise HTTPException(409, 'invalid_transition')
            role, actor = ('agent', operator.id) if operator else ('user', user_id)
            previous = next((m for m in ticket['messages'] if m['id'] == payload.messageId), None)
            if previous:
                if (previous['text'], previous['actor']) != (payload.text.strip(), actor):
                    raise HTTPException(409, 'chat_conflict')
                return self._public(ticket)
            if not payload.text.strip(): raise HTTPException(422, 'validation')
            if len(ticket['messages']) >= 100: raise HTTPException(429, 'chat_limit')
            if operator:
                if ticket['assignedTo'] not in (None, operator.id): raise HTTPException(409, 'chat_assigned')
                ticket['assignedTo'] = operator.id
                ticket['status'] = 'active'
            ticket['messages'].append({'id': payload.messageId, 'text': payload.text.strip(), 'role': role,
                'actor': actor, 'name': operator.name if operator else ticket['customerName'], 'at': now()})
            return self._public(ticket)
