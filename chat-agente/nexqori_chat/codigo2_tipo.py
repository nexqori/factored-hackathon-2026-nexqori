"""Código 2: solicitud/consulta, reclamo o solicitud no entendida; no ejecuta acciones."""

def detectar_tipo(context, providers):
    return providers.choice('codigo2.tipo', context,
        'Decide si la necesidad actual es una consulta/solicitud o un reclamo. '
        'Seguimiento informativo de un caso existente es consulta; iniciar una disputa, exigir corrección, '
        'denunciar cargo no reconocido, pedir devolución por una falla o expresar queja sobre un perjuicio es reclamo. '
        'En pedidos mixtos con reclamo prioriza reclamo. Respuestas breves a una pregunta pendiente se interpretan '
        'en ese contexto; desconocido si no se entiende qué aporta. No confundas reporte/documento con reclamo.',
        {'solicitud': 'Consulta de información o solicitud de servicio, sin tramitar una disputa.',
         'reclamo': 'Queja/disputa o solicitud de reparación por un problema; rama pendiente.',
         'desconocido': 'No se entiende la solicitud ni la respuesta a la pregunta pendiente.'})
