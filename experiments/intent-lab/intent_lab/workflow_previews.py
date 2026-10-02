"""Allowlisted activation descriptions only. No IO and no callable bank adapters."""
from backend.agent_routing import route_plan


def titles(es, en, pt): return dict(zip(('es','en','pt'), (es,en,pt)))


QUERY_REPLY = titles('La consulta está identificada. Revisa qué información se consultaría y qué permisos necesita; aún no se ha consultado el banco.',
                    'The inquiry is identified. Review which information would be retrieved and which permissions are needed; bank records have not been accessed.',
                    'A consulta foi identificada. Confira quais informações seriam consultadas e quais permissões são necessárias; o banco ainda não foi consultado.')


def planned(id, name, requirements, *, adapter='pending'):
    return {'id':id, 'titles':name, 'requirements':requirements, 'adapter':adapter, 'status':'would_activate', 'executed':False}


def activation_plan(stage, classification):
    plan=route_plan(classification)
    rows=plan['tools']
    if stage in ('evidence','query','action','handoff'):
        rows=[row for row in rows if (stage in ('evidence','query') and row['kind']=='read') or
              (stage=='action' and row['kind']=='prepare' and row['id']!='prepare-handoff') or
              (stage=='handoff' and row['id']=='prepare-handoff')]
        items=[planned(row['id'],row['titles'],[*row['gates'], *([row['reference']] if row['reference'] else []),
                       *(['verified_bank_evidence'] if stage=='action' else [])],adapter='authenticated_bank_required') for row in rows]
        if stage=='evidence' and classification.get('intent')=='app-support':
            items += [planned('correlate-app-logs', titles('Correlacionar sesión, intento y error','Correlate session, attempt and error','Correlacionar sessão, tentativa e erro'),['bank_session','ownership','session_reference']),
                      planned('notify-confirmed-incident', titles('Notificar sólo el fallo confirmado','Notify only the confirmed failure','Notificar apenas a falha confirmada'),['verified_error','notification_adapter','idempotency'])]
        return items
    if stage=='delivery':
        return [planned('deliver-result-and-tracking',titles('Entregar resultado y folio de seguimiento','Deliver result and tracking reference','Entregar resultado e protocolo'),['operation_result_or_pending_state','real_tracking_reference','delivery_adapter'])]
    if stage=='closure':
        return [planned('collect-satisfaction',titles('Solicitar CSAT / NPS al cerrar','Request CSAT / NPS on closure','Solicitar CSAT / NPS no encerramento'),['confirmed_closure','customer_consent','survey_adapter']),
                planned('engagement-event',titles('Señal al módulo de participación','Signal to the engagement module','Sinal ao módulo de participação'),['confirmed_closure','engagement_adapter'])]
    raise ValueError('unknown_preview_stage')
