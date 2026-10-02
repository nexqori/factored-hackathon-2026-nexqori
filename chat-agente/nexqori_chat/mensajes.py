"""Mensajes ES/EN/PT. Los placeholders no llaman a servicios ni emiten herramientas."""
PENDING = {
 'complaint': {
  'es': 'La atención de reclamos aún está pendiente de programar: falta implementar el flujo de recepción, validación y seguimiento de disputas. No se realizó ninguna acción.',
  'en': 'Complaint handling is still pending implementation: dispute intake, validation and tracking have not been connected. No action was performed.',
  'pt': 'O atendimento de reclamações ainda está pendente de programação: falta implementar o recebimento, a validação e o acompanhamento de contestações. Nenhuma ação foi realizada.'},
 'navigate': {
  'es': 'La redirección aún está pendiente de programar: falta conectar este agente con la navegación del aplicativo. No se abrió ninguna pantalla.',
  'en': 'Redirection is still pending implementation: this agent is not connected to application navigation. No screen was opened.',
  'pt': 'O redirecionamento ainda está pendente de programação: falta conectar este agente à navegação do aplicativo. Nenhuma tela foi aberta.'},
 'document': {
  'es': 'La generación del reporte o documento aún está pendiente de programar: faltan el generador, la validación del contenido y el mecanismo de entrega. No se generó ni envió ningún archivo.',
  'en': 'Report or document generation is still pending implementation: generation, content validation and delivery are not connected. No file was generated or sent.',
  'pt': 'A geração do relatório ou documento ainda está pendente de programação: faltam o gerador, a validação do conteúdo e a entrega. Nenhum arquivo foi gerado ou enviado.'},
 'human': {
  'es': 'La conexión con un agente humano aún está pendiente de programar: falta integrar el canal y la asignación de atención. No se ha conectado ni notificado a ninguna persona.',
  'en': 'Connection to a human agent is still pending implementation: the support channel and assignment service are not integrated. Nobody has been connected or notified.',
  'pt': 'A conexão com um agente humano ainda está pendente de programação: falta integrar o canal e a distribuição do atendimento. Nenhuma pessoa foi conectada ou notificada.'},
 'supervised': {
  'es': 'La ejecución de esta solicitud aún está pendiente de programar: falta integrar el formulario de confirmación, los permisos y el servicio de escritura. No se registró ni ejecutó la solicitud.',
  'en': 'Execution of this request is still pending implementation: confirmation, permissions and the write service have not been integrated. The request was not registered or executed.',
  'pt': 'A execução desta solicitação ainda está pendente de programação: falta integrar a confirmação, as permissões e o serviço de escrita. A solicitação não foi registrada nem executada.'},
 'unsupported': {
  'es': 'Esta acción aún está pendiente de programar: el esquema o servicio actual no contiene la información o capacidad operativa necesaria. No se realizó ninguna acción.',
  'en': 'This action is still pending implementation: the current schema or service lacks the required information or operational capability. No action was performed.',
  'pt': 'Esta ação ainda está pendente de programação: o esquema ou serviço atual não contém as informações ou a capacidade operacional necessária. Nenhuma ação foi realizada.'}}
ERROR = {'es': 'No pude completar la consulta por un error técnico. El proceso se detuvo y quedó identificado para revisión.',
 'en': 'I could not complete the query because of a technical error. Processing stopped and the error was identified for review.',
 'pt': 'Não consegui concluir a consulta por um erro técnico. O processo foi interrompido e o erro foi identificado para análise.'}


def accion_pendiente(kind, language):
    # TODO: implementar cada adaptador en una fase posterior. No ejecutar ni simular éxito.
    return {'status': 'pending_implementation', 'pending_kind': kind, 'text': PENDING[kind][language],
            'execution_authorized': False, 'operations_executed': []}
