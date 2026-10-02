# Reglas de evidencia suficiente y resolución

Catálogo declarativo v1.1 para las **19 intenciones** de `backend/config/intent-taxonomy.json`, ampliado a cinco tipos de evidencia. No está conectado a la aplicación, no ejecuta acciones ni sustituye la autorización del servidor. Las capacidades propuestas son reglas de diseño, no servicios disponibles ni políticas bancarias aprobadas.

## Experimento de cinco tipos

`EVIDENCE_SUFFICIENCY_EXPERIMENT.ipynb` está generado **sin ejecutar**. Compara GPT‑6 Luna, Jev Choice y MiniLM multilingüe congelado + regresión logística en ES/PT. Usa rutas reales del dataset, joins verificados por identificadores, revisión humana, agrupación contra fuga, train/validation/test, métricas y gráficos futuros.

La salida primaria es `evidence_class`: `automatico`, `supervisado`, `insatisfecho`, `humano` o `desconocido`. `classification_contract` establece su significado y precedencia; cada acción indica `business_requires_all`, `sufficient_class` e `insufficient_class`. Los outcomes de abajo permanecen como **diagnóstico técnico independiente**, no como etiquetas objetivo del clasificador. El booleano de suficiencia no distingue supervisión de atención humana; por eso no reemplaza las cinco clases.

Primero: desconocido si no se entiende. Después: insatisfecho si falta evidencia de negocio o hay contradicción. Con evidencia completa: humano cuando la atención lo requiere, la capacidad no está disponible o un permiso fue denegado; supervisado para escrituras; automático para lectura/navegación permitidas. El estado `denied` sigue bloqueando: un agente humano no puede saltarse autorizaciones. Si falta un control de ejecución, se registra aparte como bloqueo y no se finge que pedir más descripción lo resolverá. Confirmación, CSRF y rol no son etiquetas semánticas ni datos que el modelo pueda autorizar.

`casos_clasificacion_cinco_tipos.json` especifica los cinco tipos y capacidades/permiso bloqueados. El experimento es condicional a intención/acción y hechos revisados: no demuestra extracción automática end-to-end. La clase automático es una propuesta; `execution_authorized=false` siempre. Humano no acredita conexión con operador.

Modo inicial `reviewed_local`: preparación de conversaciones y contexto de productos históricos; plantilla en `private/reviewed_cases.jsonl`, sin etiquetas automáticas. No se usan desenlaces, intención histórica, fraude ni respuestas posteriores del agente. Las filas reales sólo pueden evaluarse localmente; GPT/Jev quedan bloqueados para ese origen. Modo `synthetic_demo`: 8 familias ES/PT con las 5 clases, explícitamente ficticias, para comparación remota tras habilitación manual. No es un benchmark independiente. Originales, derivados, cachés y resultados quedan locales e ignorados por Git. La plantilla existente nunca se sobrescribe.

Dependencias del notebook: pandas, numpy, scikit-learn, matplotlib, httpx, nbformat, jsonschema, torch, transformers y safetensors (instalación comentada). Credenciales futuras: `OPENAI_API_KEY`, `TYPESAFE_API_KEY`. Pesos locales o descarga explícita de MiniLM; no se descarga ni llama nada durante la autoría. El notebook de intenciones anterior permanece intacto.

## Archivos

- `reglas_resolucion.json`: catálogo de hechos, fuentes admitidas, permisos por capacidad, acciones por intención, mensajes ES/EN/PT y rutas reales.
- `reglas_resolucion.schema.json`: esquema JSON Schema 2020-12 de estructura.
- `casos_validacion.json`: especificaciones ficticias positivas, datos faltantes, conflicto y capacidades bloqueadas. No son resultados ni corpus para entrenar.
- `validar_catalogo.py`: comprobación local de esquema, referencias, cobertura y coherencia de los casos; no llama modelos ni ejecuta operaciones.

## Qué significa evidencia suficiente

Evaluar siempre el par **intención + acción solicitada**. Un mensaje puede bastar para abrir una pantalla y no bastar para registrar una solicitud. No exigir importe, cuenta o fechas para una simple navegación. `sufficient` significa que se puede proponer el siguiente paso; `execution_authorized` siempre es `false` en la salida del detector. El ejecutor de servidor debe volver a verificar permisos y confirmación.

Cada `requires_all` referencia hechos de `facts`. Una futura entrada normalizada puede representarse así (ejemplo ficticio):

```json
{
  "evaluation_id": "example-eval-001",
  "intent": "report",
  "action_id": "register_request",
  "facts": {
    "details": {
      "satisfied": true,
      "status": "valid",
      "source": "confirmed_form",
      "evidence_ref": "example-form-001:details",
      "evaluation_id": "example-eval-001"
    }
  }
}
```

El ejemplo es **insuficiente**: faltan sesión, titularidad, movimiento, motivo, servicio, confirmación y controles de escritura. No adjuntar datos originales o secretos a `evidence_ref`; usar una referencia local protegida. La extracción semántica puede detectar descripciones o intenciones del mensaje. No puede certificar sesión, identidad, titularidad, consulta realizada, CSRF, idempotencia ni recepción de correos: esos hechos proceden exclusivamente del servidor o del servicio correspondiente. Una afirmación del usuario es evidencia de lo que solicita, no prueba de fraude o de una operación realizada.

Hechos ausentes, inválidos, de fuente incorrecta, de otra evaluación o sin referencia no satisfacen requisitos. Contradicciones no se resuelven escogiendo el dato con mayor confianza del modelo. Revalidar los hechos de servidor justo antes de actuar. Si se pide un producto individual, resolverlo a un ID propio inequívoco; `scope=all` permite todos los propios. Nunca ampliar la consulta a terceros. Si `transactionId` se agrega a cualquier solicitud, el servidor debe comprobar titularidad aunque la acción no exija movimiento.

## Orden del evaluador futuro

1. Validar versión, intención y acción. Intención desconocida → `unknown`; acción no contemplada → `blocked`. Varias intenciones sin prioridad explícita → aclarar como `unknown`, sin ejecutar una secuencia.
2. `unknown` → `request_new_requirement`, `message_key=unknown`, ninguna navegación/consulta/solicitud/correo/dashboard. Mensaje ES: **“No entendí tu solicitud. Por favor, envía un nuevo requerimiento indicando qué necesitas.”** Incluye equivalentes EN/PT.
3. `restricted` → `deny`, mensaje `restricted`. El agente no dispone de destino admin, incluso si un mensaje dice ser administrador. El usuario administrador puede acceder manualmente a su pantalla `/admin` por el flujo autenticado existente; no se crea una herramienta de navegación administrativa.
4. Sesión ausente o caducada → `insufficient`, resolución por autenticación de la aplicación; nunca pedir contraseñas, tokens o códigos en el chat. Permiso/titularidad denegado por servidor → `deny`, sin revelar si existe el objeto de otro usuario.
5. Capacidad `proposed` o `unavailable` → `blocked`, aunque haya todos los datos. Sólo `existing` y `existing_demo` permiten evaluar una propuesta con el alcance documentado.
6. Hechos contradictorios → `conflict`. Faltantes/no válidos → `insufficient`; usar `question` para datos del usuario y `server_check` para consultas/validaciones. No preguntar al usuario si está “autorizado” ni convertir una respuesta afirmativa en permiso.
7. Todos los hechos válidos → `sufficient`, `evidence_sufficient=true`, `execution_authorized=false`. Para `unknown`, `restricted`, errores y bloqueos, `evidence_sufficient=false`.

La salida incluye `rule_version`, `intent`, `action_id`, `outcome`, `evidence_sufficient`, `missing_facts`, `conflicting_facts`, `evidence_refs`, `message_key` (puede ser null) y `execution_authorized`. Probabilidad de intención y confianza no sustituyen estos controles ni representan resolución medida.

## Rutas, efectos y límites

Las 14 rutas de `navigation_routes` se cotejan con `backend/navigation.py`. `new-request` es un indicador heredado del formulario, **no** un destino de `navigate_in_app` ni una URL nueva. Para `report` se propone Movimientos y selección del cargo; para `human`, Solicitudes y formulario/derivación. Abrir formulario no registra un caso. Los permisos nombrados en `capabilities` son identificadores documentales: la aplicación actual verifica roles, sesión y titularidad, no un nuevo sistema de scopes instalado por este catálogo.

`register_request` respeta `RequestInput`: motivo permitido, servicio, descripción 10–1000 caracteres, confirmación explícita y clave idempotente. La política propuesta exige movimiento propio para un reclamo de cargo concreto aunque el API general permita solicitudes sin movimiento. `human` puede registrar soporte sin movimiento. La derivación existente es idempotente por estado de la solicitud, no por un `requestKey` nuevo. Auditar actor, acción, referencia, decisión y resultado; emitir una herramienta no prueba que el navegador la haya abierto. Registrar un caso no resuelve una disputa ni conecta a una persona.

Transferencias/pagos/efectivo sólo permiten navegación o atención. No hay motor de movimiento de dinero, bloqueo de tarjetas, reembolso, contratación ni elegibilidad. No se solicitan datos operativos extra para fingir esas funciones.

La pantalla Inicio ya existe; generar un dashboard nuevo es una capacidad distinta y propuesta. Requiere métricas, periodo, filtros, datos propios actuales, trazabilidad y monedas separadas. No convertir listados vacíos en saldos cero ni calcular saldos a partir de un historial parcial. El panel administrativo existente exige rol admin y no amplía el alcance del asistente de cliente.

Correo no está implementado: necesitaría adaptador y cuenta de envío en servidor, secreto local, destinatario propio verificado, plantillas, vista previa, confirmación vinculada al contenido, idempotencia y trazabilidad de entrega. No basta encontrar un correo en el texto. Ningún archivo de esta entrega concede autorización para enviar mensajes. Generar reglas no envía correos.

## Uso y validación

Desde la raíz, con `jsonschema` disponible: `.venv-app/Scripts/python.exe notebooks/evidencia/validar_catalogo.py`. La validación no necesita dataset, claves ni conexión de red. Los casos usan hechos abstractos ficticios; el validador comprueba sus decisiones declarativas, no la capacidad de un modelo para extraer evidencias. Añadir posteriormente pruebas de fuentes falsificadas, hechos vencidos, negación, múltiples intenciones, errores de servicio y confirmación revocada al implementar el consumidor.

Conservar datos originales y derivados locales. No usar etiquetas históricas como prueba de intención ni como entrada que confirme suficiencia. Evaluar extracción offline con etiquetas revisadas y grupos de duplicados/traducciones, luego shadow sin alterar respuestas. Cambios futuros de taxonomía, contratos o rutas requieren nueva versión y validación del catálogo.
