"""Explicit owned-record replacement before a complaint is registered.

The caller validates ownership and commits the new binding atomically with the
turn. This helper only discards results tied to the previous transaction and
resumes the already selected problem contract; it never executes bank actions.
"""
import copy
from uuid import uuid4

from fastapi import HTTPException


def replace_transaction_context(previous, selection, message, max_replies):
    context = previous.get('context', {})
    # There is no selected problem contract to preserve in a query or an
    # unclassified turn. The caller starts a fresh evaluation with safe history.
    if context.get('triage', {}).get('family') != 'problem' or not context.get('contract'):
        return None
    if previous['turn'] >= max_replies or len(previous['messages']) >= 29:
        raise HTTPException(409, 'conversation_limit')
    node = next((item['node_id'] for item in reversed(previous['trace']) if item['kind'] == 'context'), None)
    if node is None or node not in previous.get('node_inputs', {}):
        raise HTTPException(409, 'conversation_context_conflict')
    state = copy.deepcopy(previous)
    state.update(bank_binding=copy.deepcopy(selection), phase='paused', next_node_id=node,
                 awaiting_node_id=None, feedback_edge_id=None, last_edge_id=None,
                 run_id=str(uuid4()), turn=state['turn'] + 1, transaction_suggestion=None,
                 claim_preview_required=True)
    state['messages'].append({'role': 'user', 'content': message})
    # The old trace remains a historical record for this same owner. Only the
    # current context can authorize a preview, and it must be freshly evaluated.
    state['context'].update(bank_evidence=None, llm={'status': 'skipped'},
                            fields=[], observations=[], missing=[], questions=[],
                            activation_plan=[], state='information', reply='')
    state['context'].pop('verified_facts', None)
    state['context'].pop('summary', None)
    return state
