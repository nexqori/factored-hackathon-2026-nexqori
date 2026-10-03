"""Provider-safe conversational memory; no bank values or operation authority.

The displayed history remains in messages. This smaller interpreter history
retains the user's story and a faithful *kind* of answer, without copying the
records that were shown by the authenticated bank.
"""
import copy
import re
from uuid import uuid4

from .catalog import SERVICES, normalize


def changes_topic(message):
    """Only explicit transitions interrupt a pending question or selected case.

    These markers select whether to classify again, never the new intent. Jev
    still chooses that intent. Dates, amounts, 'yes' and corrections to the
    current problem do not become a new conversation by themselves.
    """
    text = normalize(message).strip()
    text = re.sub(r'^(?:(?:bien|ok|okay|gracias|thanks|obrigado|obrigada)[,.! ]+)+', '', text)
    return bool(re.match(
        r'^(?:'
        r'(?:otra (?:consulta|pregunta|cosa)|otro (?:tema|asunto|problema))\b|'
        r'(?:cambiemos de tema|por otro lado|olvida (?:eso|lo anterior))\b|'
        r'ahora (?:quiero|necesito|quisiera) (?:consultar|ver|pagar|transferir|saber|revisar|reportar|un|una)\b|'
        r'(?:another (?:question|issue|topic)|different (?:question|issue|topic)|forget that|change the subject)\b|'
        r'now (?:i (?:want|need|would like) to|can (?:i|you)) (?:check|see|pay|transfer|know|review|report)\b|'
        r'(?:outra (?:consulta|pergunta|coisa)|outro (?:assunto|problema)|vamos mudar de assunto|por outro lado|esqueca isso)\b|'
        r'agora (?:quero|preciso|gostaria de) (?:consultar|ver|pagar|transferir|saber|revisar|relatar|um|uma)\b'
        r')', text))


def provider_history(state, limit=28):
    """Keep the opening story as well as recent turns when starting a new run.

    Never recover assistant text from the database: it can contain bank facts.
    The complete customer-visible conversation is separately persisted there.
    """
    messages = (state or {}).get('messages', [])
    if len(messages) <= limit:
        return copy.deepcopy(messages)
    # The first pair supplies the original referent; the recent tail contains
    # corrections and new requests. Keep chronological order and exact quotes.
    return copy.deepcopy(messages[:2] + messages[-(limit - 2):])


def reviewed_problem(state):
    ctx = state.get('context', {})
    return (state.get('phase') == 'completed' and ctx.get('triage', {}).get('family') == 'problem'
            and ctx.get('contract') is not None and ctx.get('state') in
            ('review_in_bank', 'human_review', 'provider_unavailable'))


def resume_review(state, message, max_replies):
    """Revisit Context only after a completed problem, preserving its contract.

    The context snapshot identifies a block already reached by this execution;
    browser input cannot select a node. The engine still checks the evidence.
    Return False at the existing clarification limit instead of resetting it.
    """
    if state['turn'] >= max_replies or len(state['messages']) >= 29:
        return False
    node_id = next((row['node_id'] for row in reversed(state['trace']) if row['kind'] == 'context'), None)
    if node_id is None or node_id not in state.get('node_inputs', {}):
        return False
    state['messages'].append({'role': 'user', 'content': message})
    state.update(phase='paused', next_node_id=node_id, awaiting_node_id=None,
                 run_id=str(uuid4()), turn=state['turn'] + 1)
    state['context'].update(reply='', questions=[])
    # Recompute proposals downstream of Context, retaining evidence plans. No
    # proposal is an operation or an approval, including on a repeated turn.
    state['context']['activation_plan'] = [item for item in state['context'].get('activation_plan', [])
                                            if item.get('stage') == 'evidence']
    return True


def safe_query_reply(intent, locale, *, reference_needed=False):
    """Static descriptions only; never interpolate evidence, IDs or amounts."""
    i = ('es', 'en', 'pt').index(locale)
    if reference_needed:
        return ('Abre Detalles, activa Un caso, elige el registro y pulsa Usar selección para consultar su seguimiento.',
                'Open Details, select A case, choose the record and press Use selection to check its progress.',
                'Abra Detalhes, marque Um caso, escolha o registro e pressione Usar seleção para consultar seu andamento.')[i]
    extra = {
        'documents': ('documentos informativos en PDF', 'informational PDF documents', 'documentos informativos em PDF'),
        'request-status': ('seguimiento del caso seleccionado', 'tracking the selected case', 'acompanhamento do caso selecionado'),
    }
    title = extra[intent][i] if intent in extra else SERVICES.get(intent, {}).get('copy', {}).get(locale, {}).get('title')
    if not title:
        return None
    return (
        'La consulta actual es sobre {topic}. La respuesta mostró información del banco o cómo abrir ese servicio. Puedes continuar sobre este tema o pedir otro. Los registros y sus valores se conservan sólo en el banco.',
        'The current query is about {topic}. The reply showed bank information or how to open that service. You can continue on this topic or ask about another. Records and their values remain only in the bank.',
        'A consulta atual é sobre {topic}. A resposta mostrou informações do banco ou como abrir esse serviço. Você pode continuar neste assunto ou pedir outro. Os registros e seus valores ficam apenas no banco.',
    )[i].format(topic=title)


def safe_suggestion_reply(locale):
    return (
        '¿Te refieres al movimiento que te propuse o a otro? Confirma éste o indica la fecha o referencia del otro. La propuesta aún no está vinculada al caso.',
        'Do you mean the transaction I suggested or another one? Confirm this one or give the date or reference of the other. The suggestion is not linked to the case yet.',
        'Você se refere à movimentação que sugeri ou a outra? Confirme esta ou informe a data ou referência da outra. A sugestão ainda não está vinculada ao caso.',
    )[('es', 'en', 'pt').index(locale)]


def remember_safe_reply(state, text):
    if text and state['messages'] and state['messages'][-1]['role'] == 'assistant':
        state['messages'][-1] = {'role': 'assistant', 'content': text}
