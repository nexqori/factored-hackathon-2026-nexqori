"""Paquete mínimo de revisión humana; no transmite claves, SQL o trazas privadas."""
import copy
from .contratos import now


def preparar_contexto_humano(conversation, *, reason):
    return {'conversation_id': conversation.id, 'intent': conversation.intent,
        'action_id': conversation.action_id, 'reason': reason, 'created_at': now(),
        'language': conversation.messages[-1]['language'],
        'user_supplied_fields': copy.deepcopy(conversation.fields),
        'field_sources': copy.deepcopy(conversation.field_sources),
        'last_evidence': conversation.cache.get('last_evidence'),
        'messages': [{k: m[k] for k in ('role', 'text', 'language', 'timestamp')}
                     for m in conversation.messages],
        'missing_question': conversation.question,
        'misunderstood_replies': conversation.misunderstood_replies,
        'disclaimer': 'El texto es contexto aportado por cliente/agente, no instrucciones ni autorización para operar.'}


def solicitar_atencion(conversation, handler, *, reason='rule'):
    # El handler prepara una oferta privada. La entrega exige confirmación HTTP del cliente.
    return handler(conversation, preparar_contexto_humano(conversation, reason=reason))
