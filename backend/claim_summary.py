"""Deterministic claim copy, composed inside the authenticated bank boundary."""
import hashlib
import json
import re
from datetime import timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select

from .catalog import normalize
from .models import Transaction
from .payment_history import context_comparison, comparison_text


TITLES = {
    'unrecognized-charge': ('Solicito revisar un cargo que no reconozco.', 'I request a review of a charge I do not recognize.', 'Solicito a análise de uma cobrança que não reconheço.'),
    'incorrect-charge': ('Solicito revisar el importe de un cobro.', 'I request a review of a charge amount.', 'Solicito a análise do valor de uma cobrança.'),
    'payment-status': ('Solicito revisar el estado de un pago.', 'I request a review of a payment status.', 'Solicito a análise do estado de um pagamento.'),
    'app-support': ('Reporto un problema con la aplicación.', 'I am reporting a problem with the app.', 'Relato um problema com o aplicativo.'),
    'branch-support': ('Solicito revisar un problema en una sucursal.', 'I request a review of a problem at a branch.', 'Solicito a análise de um problema em uma agência.'),
    'service-feedback': ('Solicito revisar un problema de atención.', 'I request a review of a customer service problem.', 'Solicito a análise de um problema no atendimento.'),
}
FIELDS = {
    'difference': ('Importe que indico', 'Amount I reported', 'Valor que informei'),
    'symptom': ('Problema que describo', 'Problem I described', 'Problema que descrevi'),
    'attempts': ('Lo que ya intenté', 'Steps I already tried', 'O que já tentei'),
    'location': ('Lugar o canal que indico', 'Location or channel I reported', 'Local ou canal que informei'),
}
NEXT = ('Puedes seguir el estado en Mis reclamos. El caso queda pendiente de revisión; el registro no confirma una devolución ni que el problema esté resuelto.',
        'Track the status in My complaints. The case is awaiting review; registration does not confirm a refund or that the problem is resolved.',
        'Acompanhe o estado em Minhas reclamações. O caso aguarda análise; o registro não confirma uma devolução nem que o problema foi resolvido.')


def preview_token(conversation, state, locale):
    value = {'conversation': conversation.id, 'owner': conversation.user_id,
             'transaction': conversation.transaction_id, 'version': state.get('version'),
             'run': state.get('run_id'), 'locale': locale}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def useful_observations(state):
    """Use grounded current-case declarations, never prior queries or assent."""
    messages = state.get('messages', [])
    # Intake snapshots preserve the start of this case across clarification turns.
    floor = 0
    for node in state.get('record', {}).get('graph', {}).get('nodes', []):
        if node['kind'] in ('intake', 'triage'):
            initial = state.get('node_inputs', {}).get(node['id'], {}).get('messages', [])
            floor = max(floor, max((i for i, m in enumerate(initial) if m['role'] == 'user'), default=0))
    found = {}
    for item in state.get('context', {}).get('observations', []):
        field, index, quote = item.get('field'), item.get('message_index'), item.get('quote', '')
        if field not in FIELDS or type(index) is not int or not floor <= index < len(messages):
            continue
        source = messages[index]
        if source['role'] != 'user' or not quote.strip() or quote not in source['content']:
            continue
        value = ' '.join(quote.split())
        cleaned = ' '.join(re.sub(r'[^\w\s]', ' ', normalize(value)).split())
        if re.fullmatch(r'(?:si|yes|sim|no|nao|ok|okay|correcto|correct|eso|este|this one|esse|es este|si es este|yes this one|sim e este)', cleaned):
            continue
        if '?' in value or '¿' in value:
            continue
        # A quoted value remains a declaration, not a verified banking fact.
        found[field] = (index, value[:180]) if index >= found.get(field, (-1, ''))[0] else found[field]
    return {field: value for field, (_, value) in found.items()}


def claim_preview(db, conversation, state, locale):
    i = ('es', 'en', 'pt').index(locale)
    intent = state['context']['intent']
    lines = [TITLES[intent][i]]
    reference = state.get('bank_binding', {}).get('transaction_id')
    if reference != conversation.transaction_id:
        raise HTTPException(409, 'flow_not_ready')
    operation = None
    if reference:
        tx = db.scalar(select(Transaction).where(Transaction.id == reference, Transaction.user_id == conversation.user_id))
        if not tx:
            raise HTTPException(404, 'not_found')
        stamp = tx.occurred_at if tx.occurred_at.tzinfo else tx.occurred_at.replace(tzinfo=timezone.utc)
        date = stamp.astimezone(ZoneInfo('America/Mexico_City')).strftime('%d/%m/%Y')
        amount = f'{abs(Decimal(tx.amount_minor)) / 100:,.2f}'
        if locale == 'pt':
            amount = amount.translate(str.maketrans({',': '.', '.': ','}))
        status = {'completed': ('realizado', 'completed', 'concluído'),
                  'pending': ('pendiente', 'pending', 'pendente'),
                  'declined': ('rechazado', 'declined', 'recusado')}[tx.status][i]
        operation = f'{tx.merchant} · {tx.currency} {amount} · {date} · {tx.id}'
        lines.append(('Movimiento registrado: ', 'Recorded transaction: ', 'Movimentação registrada: ')[i] + operation + f' · {status}.')
    history = comparison_text(context_comparison(state, reference), locale, compact=True)
    if history: lines.append(history)
    for field, quote in useful_observations(state).items():
        line = FIELDS[field][i] + ': ' + quote
        if len('\n\n'.join([*lines, line])) <= 1000:
            lines.append(line)
    return {'summary': '\n\n'.join(lines), 'intent': intent, 'transactionId': reference,
            'operationLabel': operation, 'nextStep': NEXT[i], 'previewToken': preview_token(conversation, state, locale)}


def confirmation_text(case_id, summary, locale, linked=False):
    i = ('es', 'en', 'pt').index(locale)
    heading = (('Esta conversación quedó vinculada al caso {id}.', 'This conversation is now linked to case {id}.', 'Esta conversa foi vinculada ao caso {id}.')
               if linked else ('Registré tu reclamo con el número de caso {id}.', 'I registered your complaint with case number {id}.', 'Registrei sua reclamação com o número de caso {id}.'))
    return heading[i].format(id=case_id) + '\n\n' + NEXT[i]


def review_message(db, conversation, state, locale):
    """Customer-facing findings; never add this bank-enriched text to provider history."""
    i = ('es', 'en', 'pt').index(locale)
    preview = claim_preview(db, conversation, state, locale)
    problems = {
        'unrecognized-charge': ('Me indicas que no reconoces este cargo.', 'You told me you do not recognize this charge.', 'Você informou que não reconhece esta cobrança.'),
        'incorrect-charge': ('Me indicas que el importe cobrado no coincide con lo que esperabas.', 'You told me the charged amount differs from what you expected.', 'Você informou que o valor cobrado difere do esperado.'),
        'payment-status': ('Quieres que revisemos qué ocurrió con este pago.', 'You want us to review what happened with this payment.', 'Você quer que verifiquemos o que aconteceu com este pagamento.'),
        'app-support': ('Reportaste un problema con la aplicación.', 'You reported a problem with the app.', 'Você relatou um problema com o aplicativo.'),
        'branch-support': ('Reportaste un problema en una sucursal.', 'You reported a problem at a branch.', 'Você relatou um problema em uma agência.'),
        'service-feedback': ('Reportaste un problema con la atención recibida.', 'You reported a problem with the service you received.', 'Você relatou um problema com o atendimento recebido.'),
    }
    comparison = context_comparison(state, conversation.transaction_id)
    lines = [problems[preview['intent']][i]]
    if comparison and comparison.get('status') == 'sufficient':
        avg = comparison['averageMinor'] / 100
        delta = comparison['differenceMinor'] / 100
        current = avg + delta
        lines.append((f'Promedio de {comparison["count"]} pagos anteriores: {avg:.2f} {comparison["currency"]}.',
                      f'Average of {comparison["count"]} previous payments: {avg:.2f} {comparison["currency"]}.',
                      f'Média de {comparison["count"]} pagamentos anteriores: {avg:.2f} {comparison["currency"]}.')[i])
    if comparison and comparison.get('status') == 'sufficient':
        lines.append((f'Este cargo: {current:.2f}; diferencia: {delta:.2f} {comparison["currency"]}.',
                      f'This charge: {current:.2f}; difference: {delta:.2f} {comparison["currency"]}.',
                      f'Esta cobrança: {current:.2f}; diferença: {delta:.2f} {comparison["currency"]}.')[i])
    lines.append(('El borrador está listo en Mis reclamos. Puedes corregirlo antes de confirmar el envío.',
                  'The draft is ready in My complaints. You can edit it before confirming submission.',
                  'O rascunho está pronto em Minhas reclamações. Pode corrigir antes de confirmar o envio.')[i])
    return '\n\n'.join(lines)
