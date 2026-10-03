"""The shared support diagram. Selecting an example never replaces this graph."""


def support_workflow_v2():
    from .workflow_editor import Graph, text, PROBLEM_PORTS
    def node(id, kind, labels, x, y, config=None):
        return {'id': id, 'kind': kind, 'label': text(*labels), 'position': {'x': x, 'y': y}, 'config': config or {}}
    nodes = [
        node('start','start',('Conversación del cliente','Customer conversation','Conversa do cliente'),0,250),
        node('triage','triage',('¿Consulta o queja?','Inquiry or complaint?','Consulta ou reclamação?'),220,250),
        node('complaint_route','condition',('¿Es una queja o problema?','Is it a complaint or problem?','É uma reclamação ou problema?'),440,250,{'predicate':'triage_is','value':'problem'}),
        node('jev','jev',('Identificar el problema','Identify the problem','Identificar o problema'),660,100,{'scope':'problem'}),
        node('case_route','case_router',('Derivar según el caso','Route by case','Encaminhar por caso'),880,35),
        node('context','context',('Reunir contexto del caso','Gather case context','Reunir contexto do caso'),1410,220),
        node('human','condition',('¿No se puede aclarar?','Unable to clarify?','Não é possível esclarecer?'),1640,220,{'predicate':'needs_human'}),
        node('missing','condition',('¿Faltan datos?','Missing information?','Faltam dados?'),1870,380),
        node('ask','question',('Preguntar lo que falta','Ask for missing details','Perguntar o que falta'),2090,600),
        node('action','preview',('Proponer acción y permisos','Propose action and permissions','Propor ação e permissões'),2090,300,{'stage':'action'}),
        node('handoff','preview',('Especialista con contexto','Specialist with context','Especialista com contexto'),1870,-60,{'stage':'handoff'}),
        node('delivery','preview',('Resultado y seguimiento','Result and follow-up','Resultado e acompanhamento'),2340,180,{'stage':'delivery'}),
        node('closure','preview',('Cierre y satisfacción','Closure and satisfaction','Encerramento e satisfação'),2560,180,{'stage':'closure'}),
        node('result','response',('Mostrar siguiente paso','Show next step','Mostrar próximo passo'),2780,180,{'outcome':'current'}),
        node('query_route','condition',('¿Es una consulta o gestión?','Is it an inquiry or request?','É uma consulta ou solicitação?'),660,870,{'predicate':'triage_is','value':'query'}),
        node('query_case','jev',('Identificar la consulta','Identify the inquiry','Identificar a consulta'),900,870,{'scope':'query'}),
        node('query_scope','condition',('¿Consulta identificada?','Inquiry identified?','Consulta identificada?'),1140,870,{'predicate':'family_is','value':'query'}),
        node('service_scope','condition',('¿Gestión identificada?','Request identified?','Solicitação identificada?'),1410,1100,{'predicate':'family_is','value':'service'}),
        node('query_plan','preview',('Consulta e historial','Inquiry and history','Consulta e histórico'),1640,870,{'stage':'query'}),
        node('clarify','question',('Precisar la necesidad','Clarify the need','Esclarecer a necessidade'),900,1130,{'mode':'custom','text':text('¿Quieres consultar información o reportar un problema? Cuéntame qué necesitas revisar primero.','Would you like information or to report a problem? Tell me what you need to review first.','Quer consultar informações ou relatar um problema? Conte o que precisa revisar primeiro.')}),
    ]
    labels = [
        ('Cargo no reconocido · investigar riesgo','Unrecognized charge · investigate risk','Cobrança desconhecida · investigar risco'),
        ('Importe incorrecto · contrastar histórico','Incorrect amount · compare history','Valor incorreto · comparar histórico'),
        ('Pago dudoso · revisar intento','Uncertain payment · review attempt','Pagamento incerto · revisar tentativa'),
        ('Fallo de app · logs y evidencias','App error · logs and evidence','Falha do app · logs e evidências'),
        ('Atención en sucursal · revisar visita','Branch support · review visit','Atendimento na agência · revisar visita'),
        ('Experiencia de atención · recuperar contexto','Service experience · retrieve context','Experiência de atendimento · recuperar contexto'),
    ]
    nodes += [node('contract_'+str(i),'contract',label,1160,-440+i*200,{'intent':intent}) for i,(intent,label) in enumerate(zip(PROBLEM_PORTS,labels))]
    links=[('start','triage','next'),('triage','complaint_route','next'),('complaint_route','jev','yes'),('complaint_route','query_route','no'),
           ('jev','case_route','next'),('case_route','clarify','otherwise'),('query_route','query_case','yes'),('query_route','clarify','no'),
           ('query_case','query_scope','next'),('query_scope','query_plan','yes'),('query_scope','service_scope','no'),('service_scope','query_plan','yes'),('service_scope','clarify','no'),
           ('query_plan','delivery','next'),('context','human','next'),('human','handoff','yes'),('human','missing','no'),
           ('missing','ask','yes'),('missing','action','no'),('ask','context','reply'),('handoff','delivery','next'),('action','delivery','next'),
           ('delivery','closure','next'),('closure','result','next')]
    for i,intent in enumerate(PROBLEM_PORTS): links += [('case_route','contract_'+str(i),intent),('contract_'+str(i),'context','next')]
    return Graph.model_validate({'name':text('Flujo de atención','Support workflow','Fluxo de atendimento'),'nodes':nodes,
                                'edges':[{'id':f'm{i}','source':a,'target':b,'port':p} for i,(a,b,p) in enumerate(links)]}).model_dump()


def support_workflow():
    """Classify and route in one block while retaining the original problem branches."""
    from .workflow_editor import Graph, text
    graph=support_workflow_v2()
    removed={'complaint_route','query_route'}
    graph['nodes']=[node for node in graph['nodes'] if node['id'] not in removed]
    for node in graph['nodes']:
        if node['id']=='triage':
            node.update(kind='intake',label=text('¿Consulta o problema?','Inquiry or problem?','Consulta ou problema?'))
        elif node['position']['x']>=440:
            node['position']['x']-=220
    graph['edges']=[edge for edge in graph['edges'] if edge['source'] not in removed|{'triage'} and edge['target'] not in removed]
    graph['edges'] += [{'id':'intake_'+family,'source':'triage','target':target,'port':family}
                       for family,target in [('problem','jev'),('query','query_case'),('clarification','clarify')]]
    return Graph.model_validate(graph).model_dump()
