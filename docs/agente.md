# Chat de consulta autenticado

La entrada de la aplicación es `POST /api/assistant`. `backend/chat_gateway.py` conecta la cookie HttpOnly validada en servidor con `chat-agente/nexqori_chat/codigo1_orquestador.py`. El frontend no define identidad, permisos, token ni historial confiable. `conversationId` sólo referencia estado de la misma sesión; otra sesión, incluso del mismo usuario, no puede reutilizarlo.

## Flujo

1. Jev clasifica solicitud/reclamo/desconocido.
2. Jev selecciona intención y acción usando los contratos copiados de `chat-agente/config/`.
3. OpenAI extrae campos sustentados en el texto; Jev clasifica evidencia y el código verifica mínimos. Si faltan datos, pregunta y conserva el contexto. Tras tres respuestas no entendidas se ofrece compartir contexto con atención humana.
4. El lector PostgreSQL recupera registros propios con SQL fijo parametrizado y transacción de sólo lectura. Verifica sesión y relaciones de titularidad.
5. OpenAI redacta la respuesta con referencias a los hechos. React muestra texto y controles de descarga PDF/confirmación de atención; no ejecuta navegación ni operaciones bancarias.

Reclamos, navegación y operaciones supervisadas siguen pendientes. La acción document genera PDF propio con el código 6; human prepara contexto con el código 7, que sólo se comparte en la bandeja administrativa tras confirmación del cliente. Ambos se describen en [chat-agente](../chat-agente/README.md#pdf-y-atención-humana-en-la-aplicación). No se llaman servicios de escritura. El chat no modifica productos, solicitudes, mensajes, auditoría ni permisos. Los formularios manuales del aplicativo mantienen sus controles originales.

## Configuración y límites

La [guía de activación](../README.md#chat-conectado-a-chat-agente) detalla variables y datos enviados a proveedores. El valor inicial es `CHAT_AGENT_MODE=rules`, sin envío externo. `agent` requiere `CHAT_AGENT_ALLOW_EXTERNAL_DATA=true`, claves TypeSafe/OpenAI y acceso a los modelos definidos en Settings. Añadir una clave no activa el orquestador. No se aplican los interruptores `INTENT_*` a este puente.

El modo `rules` conserva el clasificador previo como baseline local: saldo propio, aclaración de desconocidos y avisos pendientes, sin navegación. Un error del modo `agent` no activa el baseline automáticamente; detiene el turno y devuelve una referencia de traza. Los juicios probabilísticos no son precisión medida ni permisos.

La sesión se revalida antes de procesar y antes de entregar la respuesta del agente. CSRF, origen y rol cliente siguen siendo obligatorios. El token no entra en prompts; los datos de otros usuarios se excluyen en las consultas. Los modelos no generan SQL ni autorizan operaciones.

El estado vive sólo en memoria, separado por cookie, en un único proceso. Se descarta en logout/reinicio y se purga por inactividad al recibir otro turno; no hay garantía de borrado temporizado sin tráfico. Se limita a 100 sesiones, 60 turnos por sesión retenida y 40 mensajes por conversación. Hay un turno concurrente por sesión y hasta diez llamadas de proveedor por turno, con timeout de 20 segundos por llamada. El lector limita filas y tiempo SQL. Los errores se registran con código/origen y traceId; las respuestas públicas excluyen prompts, SQL y trazas completas.

“Conversación nueva” reinicia el contexto del navegador; no borra registros bancarios. El historial anterior en `messages` permanece intacto y ya no se añade ni se usa como contexto. Para persistencia durable se necesita otro diseño y autorización: el adaptador experimental `persistencia.py` no está conectado.

Se conservan las utilidades de navegación anteriores para los menús y sus pruebas, pero el chat no las invoca. ES/EN/PT mantienen igual cobertura. La reproducción usa `speechSynthesis`; no hay captura de micrófono ni transcripción.

## Verificación

Pruebas con proveedores falsos: continuidad entre turnos, aclaraciones, aislamiento por sesión, rechazo de identidad/rol/historial inyectados, idempotencia, expiración durante una llamada, errores y ausencia de cambios en todas las tablas. Una prueba opt-in usa PostgreSQL real con fixtures locales. La prueba UI verifica respuestas y que el chat no cambie de ruta ni abra formularios. No prueban disponibilidad de APIs externas ni exactitud semántica de modelos reales.

La verificación local autorizada de octubre de 2026 añade una batería de 100 casos,
incluidos 20 flujos con Jev/OpenAI reales, y un recorrido de navegador con PDF y
atención humana. Sus resultados y scripts locales están en
`chat-agente/private/INFORME_PRUEBAS.md`, excluidos de Git. La muestra no equivale
a precisión general del modelo. Los errores de proveedor siguen deteniendo el
turno; no hay fallback silencioso.

El adaptador conserva las probabilidades originales de Jev y registra cualquier
normalización por redondeo acotado. El esquema de respuesta RAG restringe las citas
a las fuentes recuperadas; una consulta sin registros exige una lista de citas
vacía. Las validaciones posteriores siguen rechazando referencias inventadas.
