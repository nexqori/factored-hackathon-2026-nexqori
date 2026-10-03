"""The same attention interpreter as the editor, hosted inside the bank's boundary.

Graph snapshots and turns live in PostgreSQL. Neither cookies nor bank evidence
are passed to providers. This adapter offers reads and proposals, never payments.
"""
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from uuid import uuid4, UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm.attributes import flag_modified
from pydantic import Field
from .models import User, Product, Conversation, Message, ConversationFlow, AssistantTurn, RequestCase, AuditEvent, now
from .schemas import ChatInput, ConfirmInput, Locale
from .security import customer, customer_read, db_session
from .agent_tools import read_tool, ReadToolInput
from .catalog import SERVICES
from .assistant import answer
from .navigation import navigate_in_app
from .transaction_context import transaction_evidence, transaction_reply
from .transaction_suggestions import FINANCIAL_PROBLEMS, confirmation, choose, suggestion_reply
from .query_documents import can_document
from .query_answers import query_answer
from .query_context import apply_query_context
from .claim_summary import claim_preview, confirmation_text, preview_token, NEXT as CLAIM_NEXT
from .conversation_selection import replace_transaction_context
from .conversation_context import (changes_topic, provider_history, reviewed_problem, resume_review,
                                   safe_query_reply, safe_suggestion_reply, remember_safe_reply)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiments' / 'intent-lab'))
from intent_lab import workflow_execution as execution, workflow_editor as editor
from intent_lab.bank_context import BankReader
from intent_lab.providers import provider_status


class FlowMessage(ChatInput):
    requestKey: str = Field(min_length=16, max_length=64, pattern=r'^[a-zA-Z0-9-]+$')
    requestId: str | None = Field(default=None, min_length=1, max_length=64)
    replaceTransaction: bool = False
    updateSelection: bool = False


class RegisterClaim(ConfirmInput):
    details: str = Field(min_length=10, max_length=1000)
    requestKey: str = Field(min_length=16, max_length=64, pattern=r'^[a-zA-Z0-9-]+$')
    locale: Locale | None = None
    previewToken: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


def enabled():
    return os.getenv('BANK_ASSISTANT_FLOW', 'false') == 'true'


def workflow_record():
    # Read the saved master, but never run local diagnostic/notification blocks
    # in a customer's authenticated banking session. Existing turns keep a copy.
    directory = Path(os.getenv('BANK_FLOW_CONFIG', '.local/intent-lab'))
    pointer = directory / 'master-workflow.json'
    if pointer.is_file():
        try:
            identity = str(UUID(json.loads(pointer.read_text(encoding='utf-8'))['id']))
            record = json.loads((directory/'workflows'/f'{identity}.json').read_text(encoding='utf-8'))
            record['graph'] = editor.Graph.model_validate(record['graph']).model_dump()
        except (ValueError, KeyError, OSError): raise HTTPException(503, 'flow_configuration') from None
    else:
        record = {'id': 'nexqori-attention-v3', 'revision': 3, 'graph': editor.template()}
    if not editor.validate_graph(record['graph'])['valid'] or any(n['kind'] in ('diagnostic','notify') for n in record['graph']['nodes']):
        raise HTTPException(503, 'flow_configuration')
    return record


class SessionReader(BankReader):
    def __init__(self, db, user, conversation):
        self.db, self.conversation = db, conversation
        self.user = {'id': user.id, 'name': user.name, 'role': user.role}

    def read(self, intent, tool, language='es', reference=None):
        value = read_tool(self.db, self.user['id'], ReadToolInput(intent=intent, tool=tool, referenceId=reference,
                          conversationId=self.conversation.id, locale=language), commit=False)
        return {**value, 'observed_at': now().isoformat()}


def flow_view(row):
    if not row: return None
    value = execution.view(row.state)
    # Keep the public detail focused on result/evidence; model requests and
    # saved input snapshots remain server-side, as do private configuration paths.
    return {k: value[k] for k in ('execution','workflow_id','workflow_revision','triage','jev','state','reply','questions',
            'missing_fields','contract','trace','latency_ms','verified_facts','bank_evidence','activation_plan')} | {
        'state': 'registered' if row.request_id else value['state'],
        'suggestedTransaction': row.state.get('transaction_suggestion'),
        'selectedRequestId': row.state.get('bank_binding', {}).get('request_id'),
        'canDocument': can_document(row),
        'requestId': row.request_id, 'canRegister': not row.request_id and row.state.get('phase') == 'completed'
                       and value['triage'].get('family') == 'problem' and value['state'] in ('review_in_bank','human_review')
                       and value['jev'].get('intent') in editor.PROBLEM_PORTS}


def chat_router(conversation_view, message_view):
    router = APIRouter()

    @router.get('/api/assistant/capabilities')
    def capabilities(_user=Depends(customer_read)):
        return {'connected': enabled(), 'providers': provider_status() if enabled() else {}}

    @router.get('/api/conversations/{conversation_id}/flow')
    def result(conversation_id: str, user=Depends(customer_read), db=Depends(db_session)):
        conv = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id))
        if not conv: raise HTTPException(404, 'not_found')
        return {'flow': flow_view(db.get(ConversationFlow, conv.id))}

    @router.post('/api/assistant/flow')
    def chat(body: FlowMessage, user=Depends(customer), db=Depends(db_session)):
        if not enabled(): raise HTTPException(503, 'flow_unavailable')
        if body.replaceTransaction and (not body.conversationId or not body.transactionId):
            raise HTTPException(422, 'tool_reference_required')
        message = body.message.strip() + ('\n\n[Texto pegado / Pasted text / Texto colado]\n' + body.pastedText if body.pastedText.strip() else '')
        if not message or len(message) > 8100: raise HTTPException(422, 'invalid_message')
        # Same owner lock order as local payments. A retry cannot append a second
        # turn after a response is lost; no provider retries occur automatically.
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        fingerprint_data = body.model_dump(exclude={'requestKey'})
        # Preserve retries of turns created before the optional replacement flag.
        if not body.replaceTransaction: fingerprint_data.pop('replaceTransaction')
        if not body.updateSelection: fingerprint_data.pop('updateSelection')
        fingerprint = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()
        previous = db.get(AssistantTurn, (user.id, body.requestKey))
        if previous:
            if previous.fingerprint != fingerprint: raise HTTPException(409, 'conflict')
            return previous.response
        if body.transactionId: transaction_evidence(db, user.id, body.transactionId)
        if body.requestId and not db.scalar(select(RequestCase).where(RequestCase.id == body.requestId, RequestCase.user_id == user.id)):
            raise HTTPException(404, 'not_found')
        if body.conversationId:
            conv = db.scalar(select(Conversation).where(Conversation.id == body.conversationId, Conversation.user_id == user.id).with_for_update())
            if not conv: raise HTTPException(404, 'not_found')
            if body.transactionId and conv.transaction_id and body.transactionId != conv.transaction_id and not (body.replaceTransaction or body.updateSelection):
                raise HTTPException(409, 'conversation_context_conflict')
        else:
            conv = Conversation(id=str(uuid4()), user_id=user.id, title=message[:100], locale=body.locale, transaction_id=body.transactionId)
            db.add(conv); db.flush()
            db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, conversation_id=conv.id, action='conversation_started'))
        row = db.get(ConversationFlow, conv.id)
        previous_request = row.state.get('bank_binding', {}).get('request_id') if row else None
        selection_changed = body.updateSelection and (body.transactionId != conv.transaction_id or body.requestId != previous_request)
        replacing = bool((body.replaceTransaction and body.transactionId != conv.transaction_id)
                         or (selection_changed and (conv.transaction_id or previous_request)))
        if (replacing or selection_changed) and row and row.request_id:
            raise HTTPException(409, 'conversation_context_conflict')
        if selection_changed:
            db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, conversation_id=conv.id,
                              transaction_id=body.transactionId, request_id=body.requestId, action='chat_context_changed'))
        proposed = row.state.get('transaction_suggestion') if row else None
        dismissed = list(row.state.get('dismissed_transaction_ids', [])) if row else []
        selected_id = body.transactionId
        reply_to_proposal = confirmation(body.message) if not body.pastedText.strip() else None
        if proposed and not conv.transaction_id and not selected_id and not row.request_id and not body.updateSelection:
            if reply_to_proposal == 'yes':
                selected_id = proposed['id']
                transaction_evidence(db, user.id, selected_id)
            elif reply_to_proposal == 'no':
                dismissed = list(dict.fromkeys([*dismissed, proposed['id']]))[-20:]
        if selected_id:
            if not conv.transaction_id or replacing:
                db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, conversation_id=conv.id,
                                  transaction_id=selected_id, action='chat_transaction_changed' if replacing else 'chat_transaction_selected'))
            conv.transaction_id = selected_id
        elif body.updateSelection:
            conv.transaction_id = None
        selection = {'owner_id': user.id, 'transaction_id': conv.transaction_id,
                     'request_id': body.requestId if body.updateSelection else None if replacing else body.requestId or previous_request}
        reader = SessionReader(db, user, conv)
        registered = bool(row and row.request_id)
        # A clarification keeps the active case. An explicit change of topic is
        # classified again rather than swallowed as an answer to the old case.
        new_topic = bool(row and not registered and not replacing and changes_topic(body.message))
        if new_topic:
            dismissed = []
        continuing = row is not None and row.state['phase'] == 'waiting_reply' and not new_topic and not replacing
        reviewing = bool(row and not registered and not new_topic and not replacing and reviewed_problem(row.state))
        # Reclassification after an unresolved subtype must retain the conversation.
        # Use interpreter messages, never bank-enriched replies from the Message table.
        prior_messages = provider_history(row.state if row else None)
        previous_query = ({key: copy.deepcopy(row.state[key]) for key in ('queryDefaults','queryPeriodUnclear') if key in row.state}
                          if row and not new_topic and row.state['context'].get('triage',{}).get('family')=='query' else {})
        replacement = replace_transaction_context(row.state, selection, message, execution.MAX_REPLIES) if replacing and row else None
        state = replacement or (copy.deepcopy(row.state) if continuing or registered or reviewing else execution.create(workflow_record(), prior_messages + [{'role':'user','content':message}],
                    body.locale, thread_id=conv.id, bank_binding=selection, persist=lambda _: None))
        if replacing or (row and row.state.get('claim_preview_required')):
            state['claim_preview_required'] = True
        state['language'] = body.locale
        for key, value in previous_query.items():
            state.setdefault(key, value)
        state['transaction_suggestion'] = None
        state['dismissed_transaction_ids'] = dismissed
        state['conversation_context'] = {'mode': 'registered_case' if registered else ('replace_selection' if body.updateSelection else 'replace_transaction') if replacing else 'new_topic' if new_topic else
                                        'continue_question' if continuing else 'continue_review' if reviewing else 'classify',
                                        'source': 'provider_safe_history'}
        if registered:
            case = db.scalar(select(RequestCase).where(RequestCase.id == row.request_id, RequestCase.user_id == user.id))
            text = ('Tu mensaje queda en esta conversación vinculada al reclamo {id}. Puedes revisar su evolución en Mis reclamos. Para otro tema, inicia una conversación nueva.',
                    'Your message is saved in this conversation linked to complaint {id}. Track its progress in My complaints. Start a new conversation for a different topic.',
                    'Sua mensagem fica nesta conversa vinculada à reclamação {id}. Acompanhe o andamento em Minhas reclamações. Para outro assunto, inicie uma nova conversa.')
            state['context']['reply'] = text[('es','en','pt').index(body.locale)].format(id=case.id)
        elif reviewing and not resume_review(state, message, execution.MAX_REPLIES):
            # Preserve the review and its limits. Starting the interpreter from
            # scratch here would silently lose the contract and reset the limit.
            state['messages'] = provider_history(state) + [{'role':'user','content':message},
                {'role':'assistant','content':('El caso sigue pendiente de revisión y confirmación.',
                    'The case still needs review and confirmation.',
                    'O caso ainda precisa de revisão e confirmação.')[('es','en','pt').index(body.locale)]}]
        else:
            execution.advance(state, 'full', reply=message if continuing else None, bank_reader=reader, bank_selection=selection,
                              persist=lambda _: None, record_run=False)
        if not row:
            row = ConversationFlow(conversation_id=conv.id, user_id=user.id, state=state); db.add(row)
        else: row.state = state
        ctx = state['context']; navigation = None
        if not registered and ctx['triage'].get('family') == 'query' and ctx['jev'].get('status') == 'ok':
            evidence = reader.collect(ctx['intent'], selection, body.locale, [])
            ctx['bank_evidence'] = evidence
            balance = db.scalar(select(func.coalesce(func.sum(Product.balance_minor),0)).where(Product.user_id == user.id, Product.type.in_(('account','savings'))))
            # Jev already chose the intent. A paraphrase like "cuánto dinero tengo"
            # must still answer the balance instead of merely navigating to accounts.
            guided = answer('balance' if ctx['intent'] == 'account-balance' else message, body.locale, balance, body.currentPage)
            ctx['reply'] = guided['text']; navigation = guided['navigation']
            read_reply = query_answer(ctx['intent'], evidence, body.locale)
            if read_reply: ctx['reply'] = read_reply
            item = SERVICES.get(ctx['intent'])
            if item and item['kind'] != 'claim':
                navigation = navigate_in_app(item['target'] if item['kind'] == 'navigate' else 'services', 'customer',
                                             None if item['kind'] == 'navigate' else item['id'])
                ctx['reply'] = read_reply or (guided['text'] if ctx['intent']=='account-balance' else item['copy'][body.locale]['summary'])
            if ctx['intent'] == 'request-status':
                statuses = [r['data']['request'] for r in evidence['reads'] if r['tool']=='read-request-status']
                if statuses:
                    labels = {'received': ('Recibido','Received','Recebido'), 'in_review': ('En revisión','Under review','Em análise'), 'handed_off': ('Derivado a atención','Referred to support','Encaminhado ao atendimento')}
                    ctx['reply'] = statuses[0]['id'] + ' · ' + labels[statuses[0]['status']][('es','en','pt').index(body.locale)]
                else:
                    ctx['reply'] = ('Abre Detalles, activa Un caso, elige el registro y pulsa Usar selección.',
                                    'Open Details, select A case, choose the record and press Use selection.',
                                    'Abra Detalhes, marque Um caso, escolha o registro e pressione Usar seleção.')[('es','en','pt').index(body.locale)]
                navigation = navigate_in_app('complaints','customer')
            selected_evidence = next((r['data'] for r in evidence['reads'] if r['tool']=='read-transaction-evidence'), None)
            if selected_evidence:
                ctx['reply'] = transaction_reply(selected_evidence,body.locale)['text']
            apply_query_context(db, user.id, conv.id, state, body.locale)
            if 'navigation' in ctx: navigation = ctx['navigation']
            remember_safe_reply(state, safe_query_reply(ctx['intent'], body.locale,
                reference_needed=ctx['intent'] == 'request-status' and not any(
                    r['tool'] in ('read-request-status', 'read-transaction-evidence') for r in evidence['reads'])))
        if not registered and ctx['state'] in ('review_in_bank', 'human_review') and ctx['intent'] in editor.PROBLEM_PORTS:
            replies = {
                'review_in_bank': ('Ya reuní el contexto de tu caso. Revisa el relato y confirma el reclamo para darle seguimiento.',
                                  'I have gathered the context of your case. Review the details and confirm the complaint to track its progress.',
                                  'Já reuni o contexto do seu caso. Revise o relato e confirme a reclamação para acompanhar o andamento.'),
                'human_review': ('Tu caso necesita revisión de atención. Revisa el relato y confirma el reclamo para solicitarla.',
                                 'Your case needs a review by customer support. Review the details and confirm the complaint to request it.',
                                 'Seu caso precisa de análise do atendimento. Revise o relato e confirme a reclamação para solicitá-la.'),
            }
            ctx['reply'] = replies[ctx['state']][('es','en','pt').index(body.locale)]
            remember_safe_reply(state, ctx['reply'])
        for question in ctx.get('questions', []):
            if question['field'] in ('transaction_id','request_id'):
                question_text = {
                    'transaction_id': ('Abre Detalles, activa Un movimiento, elige el registro y pulsa Usar selección.', 'Open Details, select A transaction, choose the record and press Use selection.', 'Abra Detalhes, marque Uma movimentação, escolha o registro e pressione Usar seleção.'),
                    'request_id': ('Abre Detalles, activa Un caso, elige el registro y pulsa Usar selección.', 'Open Details, select A case, choose the record and press Use selection.', 'Abra Detalhes, marque Um caso, escolha o registro e pressione Usar seleção.'),
                }[question['field']][('es','en','pt').index(body.locale)]
                ctx['reply'] = ctx['reply'].replace(question['text'], question_text)
                question['text'] = question_text
        if (not registered and not conv.transaction_id and ctx['triage'].get('family') == 'problem'
                and ctx['jev'].get('status') == 'ok' and ctx['intent'] in FINANCIAL_PROBLEMS
                and ctx['state'] == 'ask_customer'):
            # Read-only, audited, same-owner search. It never fills verified facts
            # or the bank binding until the customer explicitly chooses a record.
            recent = reader.read('account-activity', 'read-transactions', body.locale)
            candidate = choose(recent['data']['transactions'], state['messages'], dismissed, body.locale)
            if candidate:
                state['transaction_suggestion'] = candidate
                ctx['reply'] = suggestion_reply(candidate, body.locale)
                remember_safe_reply(state, safe_suggestion_reply(body.locale))
        row.state = copy.deepcopy(state)
        # Read tools can autoflush the row before query evidence/reply is attached.
        # Explicitly mark the JSON snapshot so the restored result matches this turn.
        flag_modified(row, 'state')
        user_message = Message(id=str(uuid4()), user_id=user.id, conversation_id=conv.id, role='user', content=message, locale=body.locale)
        db.add(user_message); db.flush()
        reply = Message(id=str(uuid4()), user_id=user.id, conversation_id=conv.id, role='assistant', content=ctx['reply'], locale=body.locale)
        db.add(reply)
        for action in ('message_sent','flow_evaluated','assistant_replied'):
            db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, conversation_id=conv.id, transaction_id=conv.transaction_id, action=action))
        conv.updated_at = now(); db.flush()
        response = {'text': reply.content, 'destination': navigation['destination'] if navigation else None, 'navigation': navigation,
                    'conversation': conversation_view(conv), 'messages': [message_view(user_message), message_view(reply)], 'flow': flow_view(row)}
        db.add(AssistantTurn(user_id=user.id, request_key=body.requestKey, fingerprint=fingerprint, response=response))
        db.commit()
        return response

    @router.get('/api/conversations/{conversation_id}/claim-preview')
    def preview_claim(conversation_id: str, locale: Locale | None = None, user=Depends(customer_read), db=Depends(db_session)):
        conv = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id))
        if not conv: raise HTTPException(404, 'not_found')
        row = db.get(ConversationFlow, conv.id)
        if not row or not flow_view(row)['canRegister']: raise HTTPException(409, 'flow_not_ready')
        if row.state['context']['intent'] in FINANCIAL_PROBLEMS and not conv.transaction_id:
            raise HTTPException(409, 'flow_not_ready')
        value = claim_preview(db, conv, row.state, locale or row.state['language'])
        db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, conversation_id=conv.id,
                          transaction_id=conv.transaction_id, action='claim_previewed'))
        db.commit()
        return value

    @router.post('/api/conversations/{conversation_id}/claim')
    def register_claim(conversation_id: str, body: RegisterClaim, user=Depends(customer), db=Depends(db_session)):
        if len(body.details.strip()) < 10: raise HTTPException(422, 'details')
        db.scalar(select(User).where(User.id == user.id).with_for_update())
        conv = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id).with_for_update())
        if not conv: raise HTTPException(404, 'not_found')
        row = db.scalar(select(ConversationFlow).where(ConversationFlow.conversation_id == conversation_id, ConversationFlow.user_id == user.id).with_for_update())
        if not row: raise HTTPException(404, 'not_found')
        fingerprint = hashlib.sha256(json.dumps(body.model_dump(exclude={'requestKey'}), sort_keys=True).encode()).hexdigest()
        cached = row.state.get('claim_registration')
        if cached:
            if cached['request_key'] == body.requestKey and cached['fingerprint'] != fingerprint:
                raise HTTPException(409, 'conflict')
            return cached['response']
        # Old registered conversations may have no confirmation message yet.
        # A new explicit request backfills it once, without creating another case.
        if not row.request_id and not flow_view(row)['canRegister']: raise HTTPException(409, 'flow_not_ready')
        locale = body.locale or row.state['language']
        if not row.request_id and (body.previewToken is not None or row.state.get('claim_preview_required')):
            if body.previewToken != preview_token(conv, row.state, locale):
                raise HTTPException(409, 'claim_preview_outdated')
        intent = row.state['context']['intent']; item = SERVICES[intent]
        tx = row.state['bank_binding'].get('transaction_id')
        if tx != conv.transaction_id: raise HTTPException(409, 'flow_not_ready')
        if intent in ('unrecognized-charge','incorrect-charge','payment-status') and not tx: raise HTTPException(422, 'tool_reference_required')
        if tx: transaction_evidence(db, user.id, tx)
        existing = db.scalar(select(RequestCase).where(RequestCase.user_id == user.id, RequestCase.id == row.request_id)) if row.request_id else None
        if row.request_id and not existing: raise HTTPException(404, 'not_found')
        if not existing:
            reused_key = db.scalar(select(RequestCase).where(RequestCase.user_id == user.id, RequestCase.request_key == body.requestKey))
            if reused_key: raise HTTPException(409, 'conflict')
            existing = db.scalar(select(RequestCase).where(RequestCase.user_id == user.id, RequestCase.transaction_id == tx)) if tx else None
        linked = existing is not None
        if not existing:
            existing = RequestCase(id='NQ-'+uuid4().hex[:10].upper(), user_id=user.id, transaction_id=tx, request_key=body.requestKey,
                                   catalog_service_id=intent, service=item['category'], reason=item['reason'], details=body.details.strip(),
                                   service_data={'provider':None,'reference':'','beneficiary':'','amountMinor':None,'currency':None,'accountLast4':None,
                                                 'notes':body.details.strip(), 'workflow':{'id':row.state['record']['id'], 'version':row.state['record']['revision']}})
            db.add(existing); db.flush()
            action = 'created'
        else: action = 'conversation_linked'
        was_registered = bool(row.request_id)
        row.request_id = existing.id
        if not was_registered:
            db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, request_id=existing.id, conversation_id=conversation_id, transaction_id=tx, action=action))
        # Linking another conversation does not overwrite the original case.
        # Its confirmation still describes the newly reviewed summary, not an
        # old transcript that may have been stored by an earlier application.
        summary = claim_preview(db, conv, row.state, locale)['summary'] if was_registered else body.details.strip()
        reply = Message(id=str(uuid4()), user_id=user.id, conversation_id=conversation_id, role='assistant',
                        content=confirmation_text(existing.id, summary, locale, linked), locale=locale)
        db.add(reply)
        db.add(AuditEvent(id=str(uuid4()), user_id=user.id, actor_id=user.id, request_id=existing.id,
                          conversation_id=conversation_id, transaction_id=tx, action='assistant_replied'))
        conv.updated_at = now()
        db.flush()
        response = {'id': existing.id, 'message': message_view(reply), 'summary': summary,
                    'nextStep': CLAIM_NEXT[('es','en','pt').index(locale)], 'flow': flow_view(row)}
        # This bank-enriched response is durable but never joins provider messages.
        state = copy.deepcopy(row.state)
        state['claim_registration'] = {'request_key': body.requestKey, 'fingerprint': fingerprint, 'response': response}
        row.state = state
        flag_modified(row, 'state')
        db.commit()
        return response

    return router
