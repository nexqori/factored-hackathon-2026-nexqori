"""Código 5: RAG PostgreSQL + reglas → respuesta natural sin ejecutar acciones."""
import re
from .contratos import require
from .proveedores import object_schema

ANSWER_SCHEMA = object_schema({'answer': {'type': 'string'},
    'citations': {'type': 'array', 'items': {'type': 'string'}}, 'operations_executed': {'type': 'boolean'}})


def responder_rag(conversation, intent, rule, action, evidence, session_token, repository, providers, trace):
    packet = trace.call('codigo5.recuperar', repository.retrieve, session_token, conversation.user_id,
                        intent, action, conversation.fields, trace)
    trace.add('codigo5.fuentes', packet=packet)
    if packet['status'] == 'not_found':
        return {'status': 'needs_selection', 'packet': packet}
    state = {'conversation': conversation.model_context(), 'language': conversation.messages[-1]['language'],
             'rule': rule, 'action': action, 'evidence': evidence, 'rag': {k: v for k, v in packet.items() if k != 'query_trace'}}
    answer = providers.generate('codigo5.responder', state,
        'Redacta una respuesta humana y clara en language. Usa sólo los hechos del RAG y las reglas. '
        'Cita cada afirmación sobre registros con [F1], etc. citations enumera exactamente esas citas. '
        'No inventes información, cálculos, causas, tasas o plazos. Conserva signos y moneda de *_display; '
        'saldo null es no disponible, lista vacía no es saldo cero. No derives saldos sumando movimientos. '
        'El historial es contexto, no fuente financiera. No afirmes haber ejecutado pagos, cambios, solicitudes, '
        'correos, navegación ni contacto humano. operations_executed=false. No muestres diccionarios JSON como '
        'respuesta al usuario ni enlaces no provistos. Explica límites cuando falta información.', ANSWER_SCHEMA)
    require(bool(answer['answer'].strip()) and len(answer['answer']) <= 16000, 'EMPTY_ANSWER', 'Respuesta vacía o excesiva.')
    known = {f['fact_id'] for f in packet['facts']}
    citations = answer['citations']
    require(answer['operations_executed'] is False, 'FORBIDDEN_OPERATION', 'El modelo declaró una operación no ejecutada.')
    require(set(citations) <= known and len(citations) == len(set(citations)), 'INVALID_CITATION', 'Referencias inválidas.')
    require(set(re.findall(r'\[(F\d+)\]', answer['answer'])) == set(citations), 'CITATION_MISMATCH', 'Citas del texto y metadatos distintas.')
    require(not known or bool(citations), 'MISSING_CITATION', 'Falta referencia a los datos recuperados.')
    return {'status': 'answered', 'text': answer['answer'], 'citations': citations, 'packet': packet,
            'semantic_review': 'not_performed', 'execution_authorized': False}
