"""Schedule the saved editor graph with LangGraph; keep host-owned checkpoints.

The bank commits its snapshot with the conversation, audit and idempotent turn.
The editor saves the same JSON schema after each block. A second checkpointer
would split those transactions. Resume therefore enters at the server's saved
next_node_id, never by replaying the start or accepting a client-selected route.
"""
import json
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import version
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy
from langsmith.run_helpers import tracing_context

MAX_BLOCKS = 40
RUNTIME_VERSION = version('langgraph')


class GraphState(TypedDict):
    execution: dict
    remaining: int


@dataclass(frozen=True)
class RunContext:
    execute: Callable
    persist: Callable
    emit: Callable
    bank_reader: Any = None


def topology(graph):
    """Only topology is cached: no prompts, messages, sessions or bank records."""
    return json.dumps({
        'nodes': sorted(n['id'] for n in graph['nodes']),
        'edges': sorted({(e['source'], e['target']) for e in graph['edges']}),
    }, sort_keys=True)


def _route(snapshot: GraphState):
    state = snapshot['execution']
    if state['phase'] != 'running':
        return END
    return state['next_node_id']


def _block(node_id, allowed_targets):
    def execute_block(snapshot: GraphState, runtime: Runtime[RunContext]):
        state, context = snapshot['execution'], runtime.context
        if state['phase'] != 'running' or state['next_node_id'] != node_id:
            raise RuntimeError('wrong_next_node')
        # No automatic retries: provider reads and local diagnostic notifications
        # may already have happened when a persistence error reaches this point.
        context.execute(state, context.emit, context.bank_reader, context.persist)
        if state['phase'] != 'completed' and state['next_node_id'] not in allowed_targets:
            raise RuntimeError('invalid_transition')
        remaining = snapshot['remaining'] - 1
        state['version'] += 1
        if state['phase'] == 'running' and remaining == 0:
            state['phase'] = 'paused'
        context.persist(state)
        return {'execution': state, 'remaining': remaining}
    return execute_block


@lru_cache(maxsize=32)
def compile_graph(topology_json):
    spec = json.loads(topology_json)
    builder = StateGraph(GraphState, context_schema=RunContext)
    # Prefixes avoid collisions with the state keys or LangGraph's reserved nodes.
    names = {node_id: 'block__' + node_id for node_id in spec['nodes']}
    for node_id, name in names.items():
        targets = frozenset(target for source, target in spec['edges'] if source == node_id)
        builder.add_node(name, _block(node_id, targets), retry_policy=RetryPolicy(max_attempts=1))
        builder.add_conditional_edges(name, _route, {END: END, **{target: names[target] for target in targets}})
    builder.add_conditional_edges(START, _route, {END: END, **names})
    return builder.compile(name='nexqori_attention')


def run(state, mode, execute, persist, emit, bank_reader=None):
    if mode not in ('step', 'full'):
        raise ValueError('invalid_mode')
    graph = compile_graph(topology(state['record']['graph']))
    state['runtime'] = {'name': 'langgraph', 'version': RUNTIME_VERSION, 'checkpoint_schema': 1}
    # Banking context must not be exported to hosted tracing, even when a parent
    # process has tracing enabled. Our filtered node events remain the UI stream.
    with tracing_context(enabled=False):
        graph.invoke(
            {'execution': state, 'remaining': 1 if mode == 'step' else MAX_BLOCKS},
            context=RunContext(execute, persist, emit, bank_reader),
            config={'recursion_limit': MAX_BLOCKS + 2, 'max_concurrency': 1, 'callbacks': []},
        )
