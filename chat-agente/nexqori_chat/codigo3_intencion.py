"""Código 3: taxonomía sólo de solicitudes; selección de acción sin ejecutarla."""

def detectar_intencion(context, taxonomy, rules, providers):
    criteria = {i['id']: i['definition'] for i in taxonomy['intents']}
    intent = providers.choice('codigo3.intencion', context,
        'Selecciona la intención específica actual. Usa el contexto para continuar una consulta pendiente. '
        'Documentos/reportes/exportaciones corresponden a documents, no a una disputa. '
        'Si hay varias necesidades sin prioridad clara elige unknown.', criteria)
    rule = rules['rules'][intent['label']]
    if len(rule['actions']) == 1:
        action = {'label': rule['actions'][0]['id'], 'probability': None, 'confidence': None,
                  'probabilities': {}, 'model': None, 'source': 'single_allowed_action'}
    else:
        action = providers.choice('codigo3.accion', {'conversation': context, 'rule': rule},
            'Selecciona la acción concreta solicitada según el mensaje. Abrir/ir a una pantalla es navigate; '
            'pedir datos es read. Nunca ejecutar. clarify si la acción es ambigua.',
            {a['id']: a['description'] for a in rule['actions']})
    return {'intent': intent, 'action': action, 'rule': rule,
            'selected_action': next(a for a in rule['actions'] if a['id'] == action['label'])}
