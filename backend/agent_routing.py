"""Shared, side-effect-free routing policy. A classification is never authorization.

This module uses only the standard library so the isolated LAB can use the same
allowlist as the bank without importing its database or authentication runtime.
"""
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).parent
SERVICES = {s['id']: s for s in json.loads((ROOT / 'service_catalog.json').read_text(encoding='utf-8'))['items']}
CATALOG = json.loads((ROOT / 'workflow_catalog.json').read_text(encoding='utf-8'))
PROBLEMS = {item['id']: item for item in CATALOG['items']}
FALLBACKS = {'needs-clarification', 'multiple-intents', 'out-of-scope'}
VERSION = '1'


def tool(kind, titles, reference=None, route=None, gates=()):
    return {'kind': kind, 'titles': dict(zip(('es', 'en', 'pt'), titles)),
            'reference': reference, 'route': route, 'gates': list(gates)}


TOOLS = {
    'read-balances': tool('read', ('Consultar saldos propios', 'Read own balances', 'Consultar saldos próprios')),
    'read-transactions': tool('read', ('Consultar movimientos propios', 'Read own transactions', 'Consultar movimentações próprias')),
    'read-cards': tool('read', ('Consultar tarjetas enmascaradas', 'Read masked cards', 'Consultar cartões mascarados')),
    'read-request-status': tool('read', ('Consultar folio y devolución', 'Read request and refund status', 'Consultar protocolo e devolução'), 'requestId'),
    'read-transaction-evidence': tool('read', ('Revisar registros del movimiento', 'Read transaction records', 'Revisar registros da movimentação'), 'transactionId'),
    'read-service-info': tool('read', ('Consultar información del servicio', 'Read service information', 'Consultar informações do serviço')),
    'read-problem-contract': tool('read', ('Consultar procedimiento del problema', 'Read problem procedure', 'Consultar procedimento do problema')),
    'prepare-request': tool('prepare', ('Preparar solicitud para revisión', 'Prepare request for review', 'Preparar solicitação para revisão'), gates=('confirmation', 'idempotency')),
    'prepare-handoff': tool('prepare', ('Preparar derivación del folio', 'Prepare request handoff', 'Preparar encaminhamento do protocolo'), 'requestId', '/requests', ('confirmation', 'idempotency')),
    'prepare-card-block': tool('prepare', ('Revisar bloqueo de tarjeta', 'Review card blocking', 'Revisar bloqueio do cartão'), 'productId', '/cards', ('confirmation', 'password', 'idempotency')),
    'prepare-refund-review': tool('prepare', ('Revisar solicitud de devolución', 'Review refund request', 'Revisar solicitação de devolução'), 'requestId', '/requests', ('confirmation', 'idempotency', 'administrator_approval')),
}


def route_family(intent):
    if intent in PROBLEMS:
        return 'problem'
    if intent == 'request-status':
        return 'query'
    item = SERVICES.get(intent)
    if item:
        return 'query' if item['kind'] in {'navigate', 'inquiry'} else 'service'
    return 'clarification'


def tools_for(intent):
    """Return a fresh list of tool IDs; never accept tool names from model text."""
    family = route_family(intent)
    if family == 'query':
        return {
            'account-balance': ['read-balances'],
            'account-activity': ['read-transactions'],
            'my-cards': ['read-cards'],
            'request-status': ['read-request-status'],
        }.get(intent, ['read-service-info'])
    if family == 'problem':
        ids = ['read-problem-contract', 'read-request-status']
        if intent in {'unrecognized-charge', 'incorrect-charge', 'payment-status', 'app-support'}:
            ids.append('read-transaction-evidence')
        if intent == 'unrecognized-charge':
            ids.append('read-cards')
        ids += ['prepare-request', 'prepare-handoff']
        actions = PROBLEMS[intent].get('availableActions', [])
        if 'block-card' in actions:
            ids.append('prepare-card-block')
        if 'request-refund' in actions:
            ids.append('prepare-refund-review')
        return ids
    if family == 'service':
        return ['read-service-info', 'prepare-request']
    return []


def route_plan(classification, *, source='jev'):
    """Propose a route from a validated intent. No lookup, network or operation."""
    candidate = classification.get('intent')
    valid = classification.get('status') == 'ok' and isinstance(candidate, str) and candidate in (SERVICES.keys() | FALLBACKS | {'request-status'})
    intent = candidate if valid else None
    family = route_family(intent)
    steps = []
    for tool_id in tools_for(intent):
        item = deepcopy(TOOLS[tool_id])
        if tool_id == 'prepare-request':
            item['route'] = f'/services/catalog/{intent}'
        steps.append({'id': tool_id, **item, 'status': 'not_executed',
                      'execution': 'authenticated_bank' if item['kind'] == 'read' else 'review_in_bank',
                      'owner_scope': 'authenticated_customer',
                      'gates': ['bank_session', 'ownership', *item['gates']]})
    return {'version': VERSION, 'source': source, 'intent': intent, 'family': family,
            'status': 'unavailable' if not valid else 'needs_clarification' if family == 'clarification' else 'proposed',
            'contract': {'id': intent, 'version': CATALOG['version']} if family == 'problem' else None,
            'tools': steps, 'executed_tools': [], 'executed_operations': [], 'authorizes_execution': False}
