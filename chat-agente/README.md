# Chat agente Nexqori

Implementación Python independiente en cinco componentes reutilizables. **Los programas, pruebas, consultas, modelos y SQL no se ejecutaron durante la autoría.** No está conectada a `/api/assistant`; el backend y sus respuestas actuales permanecen intactos.

## Componentes

| Código | Archivo en `nexqori_chat/` | Función |
| --- | --- | --- |
| 1 | `codigo1_orquestador.py` | `ChatAgent.handle_message(...)`: un turno del chatbot; `solicitud_predeterminada(...)`: entrada manual con usuario y timestamp |
| 2 | `codigo2_tipo.py` | `detectar_tipo(...)`: Jev distingue solicitud/consulta, reclamo y desconocido |
| 3 | `codigo3_intencion.py` | `detectar_intencion(...)`: Jev selecciona intención y acción del contrato copiado |
| 4 | `codigo4_evidencia.py` | `clasificar_evidencia(...)`: Jev devuelve las cinco clases; OpenAI extrae campos anclados a citas y redacta preguntas |
| 5 | `codigo5_rag.py` | `responder_rag(...)`: PostgreSQL recupera información propia y GPT-6 Luna genera la respuesta natural |

`postgres.py` concentra consultas y autorización; `proveedores.py` valida respuestas y registra llamadas; `contratos.py` define mensajes, conversación y trazas. Importar estos módulos no conecta servicios ni inicia programas. Las funciones de los notebooks se adaptaron al flujo sin importar/ejecutar celdas, entrenamiento ni evaluaciones.

## Flujo y límites

1. Validar mensaje y sesión real de cliente. Derivar el titular de la cookie y contrastarlo con `user_id`; no aceptar permisos o historial aportados por el modelo.
2. Código 2 clasifica cada turno considerando la pregunta pendiente. Un reclamo se detiene aquí, sin recuperar datos bancarios ni ejecutar los códigos 3–5. Se imprime/devuelve que el tratamiento de reclamos está pendiente y por qué. Seguimiento informativo de un caso existente se considera consulta; iniciar disputa/corrección/devolución por un perjuicio se considera reclamo.
3. Para solicitudes, código 3 usa la taxonomía adaptada. `report` (reclamo) se elimina; `documents` significa reporte/documento/exportación. Una acción única se selecciona en código sin atribuirle probabilidad de modelo.
4. El LLM propone campos con citas literales del último mensaje. Se verifican identificadores, tipos y procedencia, y Jev evalúa evidencia. Los requisitos deterministas pueden convertir una predicción suficiente en `insatisfecho`; una predicción nunca concede permisos.
5. `insatisfecho` devuelve `awaiting_user` y una pregunta específica basada en las reglas. El chatbot presenta la pregunta y pasa la siguiente respuesta a la misma conversación. Se vuelve a clasificar. No hay un loop que invente respuestas del usuario.
6. Si no se entiende una respuesta a la pregunta pendiente, se pide reformular. Se permiten **dos respuestas adicionales**: tras tres respuestas consecutivas no entendidas, se devuelve el punto pendiente de atención humana. Una respuesta pertinente reinicia ese contador. Hay además un máximo de ocho rondas de aclaración para evitar ciclos sin progreso; también termina en atención humana pendiente.
7. Sólo una lectura con evidencia suficiente alcanza código 5. Se revalida sesión y titularidad, se ejecuta SQL parametrizado y el LLM redacta con referencias. Selección ajena/inexistente produce la misma petición de aclaración, sin revelar existencia de datos de terceros.

Reclamos, navegación, documentos y atención humana tienen placeholders en `mensajes.py`: **no abren pantallas, generan archivos, envían correos, notifican personas ni conectan operadores**. La respuesta contiene “aún está pendiente de programar” y explica la integración faltante. Una solicitud supervisada también queda pendiente del formulario, confirmación, permisos y adaptador de escritura: no registra un caso ni realiza operaciones monetarias.

ES/EN/PT tienen cobertura en contratos y mensajes. El canal `voice` acepta texto ya transcrito y una referencia local opcional; no implementa micrófono, transcripción ni síntesis de voz. No cambia la moneda según idioma.

## Contratos copiados y adaptados

Todos están en `config/`, con versión `2.0.0-chat-agent`:

- `intent-taxonomy.json`: copia derivada de `backend/config/intent-taxonomy.json`, sin intención `report`; añade `documents`.
- `reglas_resolucion.json`: deriva del catálogo de evidencia; reduce el contrato a consultas/solicitudes, mínimos por acción, cinco clases, preguntas ES/EN/PT, destinos declarativos y placeholders.
- `reglas_resolucion.schema.json`: esquema adaptado para validar ese contrato reducido; no es intercambiable con el esquema original v1.1.0.
- `casos_clasificacion_cinco_tipos.json`: nueve especificaciones con IDs únicos y las cinco clases, sin reclamos. El archivo repetido en la petición se copia/adapta una sola vez. No son resultados de modelos.
- `provenance.json`: fuentes y hashes de los contratos/notebooks tomados como referencia.

Las reglas originales y los notebooks no se modifican. `fresh_data` y titularidad no se simulan como hechos extraídos del usuario: se verifican en la recuperación. La evidencia del código 4 expresa suficiencia para iniciar una consulta/propuesta, no que la base ya devolvió información ni que una acción fue autorizada.

## Configuración y credenciales

`requirements.txt` declara dependencias del paquete. Crear un entorno aparte e instalarlo sólo cuando se decida ejecutar. Desde `chat-agente` el paquete es importable como `nexqori_chat`.

| Configuración | Origen/uso |
| --- | --- |
| `OPENAI_API_KEY` | Ya existe en `.env.example` raíz; preguntas, extracción y GPT-6 Luna |
| `TYPESAFE_API_KEY` | Ya existe en `.env.example` raíz; Jev `jev-1.13.0` |
| `DATABASE_URL` | URL completa opcional; si falta, `Settings.from_env()` la construye con la contraseña de aplicación y los valores de conexión |
| `APP_DATABASE_PASSWORD` | Se reutiliza desde `.env` raíz para construir la URL del rol `nexqori_app`; no se usa la contraseña del administrador |
| `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE` | Opcionales: defaults `db`, `5432`, `nexqori_app`, `nexqori`; ajustar host/puerto fuera de la red Docker |
| `session_token` | Argumento privado desde la cookie `nexqori_session`; no va en mensajes, trazas, prompts ni persistencia |
| `Settings.allow_api` | Por defecto `False`; habilitación explícita de llamadas |
| `Settings.allow_external_data` | Por defecto `False`; habilitación explícita del envío de contexto y datos propios a TypeSafe/OpenAI |

El `.env.example` de esta carpeta documenta las variables consumidas. No se modificó el archivo raíz ni se inventó una sesión. Tanto CLI como chatbot usan `Settings.from_env()`: lee `.env` raíz, luego `chat-agente/.env` si existe y finalmente el entorno del proceso, en ese orden de prioridad creciente. Los valores vacíos no borran valores previos. No modifica `os.environ`, no imprime ni guarda la URL resultante y no conecta al cargar configuración. Cambiar claves no activa llamadas a modelos.

La precedencia de conexión es: argumento `database_url=...` → `DATABASE_URL` resuelta de esos orígenes → construcción con `APP_DATABASE_PASSWORD` y `PG*`. Si existe una URL completa, los campos `PG*` no la reemplazan. La contraseña y los componentes de usuario/base se codifican para URL; se conservan literalmente caracteres como `@`, `#`, `$` o `${...}`. No se realiza interpolación entre variables de los archivos `.env`: escribir una URL completa literal o dejarla vacía para usar la construcción automática.

`backend/db.py` consume `DATABASE_URL`, pero no la crea ni la exporta como variable Python. La solución independiente reutiliza los valores de Compose sin importar SQLAlchemy ni crear el engine del backend. Con el `.env` raíz generado por el setup, no hace falta copiar de nuevo la contraseña para ejecutar dentro de la red Docker. Para ajustes independientes, copiar `chat-agente/.env.example` a `chat-agente/.env` y editar sólo lo necesario; el archivo local está excluido de Git.

Compose usa `postgresql+psycopg://nexqori_app:<password>@db:5432/nexqori`; el adaptador acepta esa forma o `postgresql://...`. Codificar los caracteres especiales de la contraseña en la URI. El host `db` sólo resuelve dentro de la red Docker y PostgreSQL no publica puerto al host. Para ejecución independiente proporcionar una conexión accesible con rol de lectura mínimo; no se alteraron puertos/Compose. Claves y conexión nunca se imprimen.

La cookie debe ser de un cliente vigente de esa misma base. No pasar `csrfToken`, `token_hash` ni contraseña como sesión. El adaptador verifica sesiones antes de clasificar y nuevamente antes de recuperar datos.

## Opción 1: solicitud predeterminada

Ejemplo de uso futuro, **no ejecutado**. Desde `chat-agente`, con entorno preparado:

```powershell
python -m nexqori_chat --user-id "ID_REAL_DE_USERS" --enable-api --allow-external-data
```

Solicita la cookie de sesión de forma oculta. El mensaje inicial es “¿Cuál es el saldo de todas mis cuentas?”, con timestamp UTC actual y `message_id` único. `--text` y `--language es|en|pt` permiten cambiarlo. El programa imprime el texto final o la pregunta; no solicita automáticamente respuestas posteriores ni escribe en la base.

También se puede usar `solicitud_predeterminada(agent, user_id=..., session_token=..., answers=[...])`. Consume respuestas sólo mientras el estado es `awaiting_user`, sin seguir ejecutando después de un error o placeholder. Sin respuestas disponibles devuelve el estado pendiente para que el cliente continúe.

## Opción 2: función para un chatbot futuro

Mantener **una instancia de servicio y su almacén en el servidor**, no crear una por mensaje. Ejemplo de integración que no registra una ruta FastAPI:

```python
from nexqori_chat.config import Settings
from nexqori_chat.postgres import PostgresRepository
from nexqori_chat.codigo1_orquestador import ChatAgent

settings = Settings.from_env(allow_api=True, allow_external_data=True)
agent = ChatAgent(settings, PostgresRepository(settings))

def on_chat_message(payload, authenticated_cookie):
    # payload contiene sólo los campos del contrato UserMessage.
    return agent.handle_message(payload, session_token=authenticated_cookie)
```

Contrato de entrada:

```json
{
  "user_id": "ID_REAL_DE_USERS",
  "text": "¿Qué movimientos tengo en todas mis cuentas?",
  "language": "es",
  "timestamp": "2026-10-02T10:00:00-05:00",
  "message_id": "identificador-unico-del-mensaje",
  "conversation_id": null,
  "channel": "text",
  "audio_ref": null
}
```

En el siguiente turno conservar el `conversation_id` devuelto y enviar un `message_id` nuevo. Para reintentar el mismo mensaje, repetir exactamente payload y message_id: no vuelve a invocar modelos dentro del mismo proceso. Reutilizar un ID con contenido distinto es error. El cliente nunca envía estado, roles del historial, resultados de Jev ni campos de autorización. Se debe derivar/proporcionar el usuario autenticado en el servidor y conservar comprobaciones de origen/CSRF y límites del backend al integrar una ruta HTTP.

La salida incluye `status`, `text`, `language`, `conversation_id`, `trace_id`, `execution_authorized=false`, `operations_executed=[]` y `persistence`. **Al navegador enviar sólo la respuesta pública necesaria**, no el paquete privado de persistencia con prompts/datos. `awaiting_user` solicita otro turno; `answered` entrega respuesta; `pending_implementation` informa integración faltante; `error` detiene la conversación. Tras error, revisar la causa y comenzar otra conversación.

## Relación con backend y dataset

Se inspeccionaron sólo encabezados locales del dataset; no se importaron registros ni se usaron etiquetas como verdad.

| Dataset | Esquema operativo | Límite |
| --- | --- | --- |
| `customers.customer_id` | `users.id` | No hay tabla de correspondencia garantizada; no usar IDs históricos como sesiones |
| `products.product_id/customer_id/product_type/current_balance` | `products.id/user_id/type/balance_minor` | Categorías, unidades monetarias y titularidad requieren ETL revisado; no importar automáticamente |
| `transactions.transaction_id/product_id/customer_id/amount/transaction_status` | `transactions.id/product_id/user_id/amount_minor/status` | Los estados/categorías originales no son equivalentes automáticamente; JOIN verifica producto y titular |
| `call_transcripts.full_text/customer_text/agent_text/detected_language` | Historial `messages` y paquete `communication` | El agente conserva texto por hablante e idioma; no usa `detected_intents` como entrada ni referencia correcta |
| `call_center_interactions.interaction_id/interaction_date/channel` | conversation_id, timestamp y channel propuestos | No existe vínculo operativo validado; no convertir resultados históricos en permisos |
| `complaints` | Fuera del flujo | No se consulta ni importa; reclamos terminan en placeholder |

RAG consulta únicamente `products`, `transactions`, `requests`, con columnas explícitas y relaciones propias. `users/sessions` sólo autentican. El contexto conversacional procede del estado de servidor; no mezcla todos los mensajes de la base que aún carecen de conversation_id. No hay tabla operativa de préstamos, inversiones o seguros; esos servicios informan capacidad pendiente.

## Persistencia posterior y columnas faltantes

Actualmente el coordinador **mantiene estado en memoria y devuelve el paquete**, no lo escribe en PostgreSQL. `MemoryStore` es local a un proceso, serializa turnos con un lock y se pierde al reiniciar. No ofrece estado compartido entre workers ni idempotencia durable. No integrar en varios workers sin sustituir ese almacén por uno transaccional persistente.

`result['persistence']` contiene el mensaje recibido, `communication.full_text`, `user_text`, `agent_text`, idioma/canal, historial completo, timestamps del cliente y servidor, conversación/versión, campos extraídos con citas, preguntas/contadores, clasificación con probabilidades y confianza, versiones/hashes, entradas/salidas de proveedores, fuentes RAG y errores rastreables. Nunca contiene claves/cookies/headers de autorización. La precisión de modelos y exactitud semántica no se han medido.

La tabla existente `messages` sólo tiene id, user_id, role, content, locale y created_at. Faltan conversation_id, client_message_id, channel, audio_ref, timestamp del cliente, versión/estado, pregunta pendiente, contadores, intención/acción/evidencia/probabilidades, procedencia, trace_id y metadatos de modelos. No sobrecargar `requests` con telemetría ni registrar reclamos para guardar conversaciones.

Se propone, **sin aplicar**, `sql/001_persistencia_propuesta.sql`:

- `chat_agent_conversations`: id, user_id, version, status, state JSONB, created_at, updated_at.
- `chat_agent_turns`: id/trace_id, conversation_id, user_id, client_message_id, payload_sha256, payload JSONB y created_at; vínculo compuesto al titular y unicidad por usuario/mensaje.

El JSONB conserva todos los detalles que hoy no tienen columnas. `persistencia.persistir_turno(conn, result['persistence'], session_token=...)` es un adaptador **opcional y no llamado automáticamente**: exige las tablas migradas, sesión vigente, mismo titular, orden de versiones e idempotencia. Sólo recibe paquetes generados por el servidor, nunca JSON del navegador. Usar conexión dedicada y rol de escritura limitado a esas dos tablas. La propuesta debe integrarse/revisarse en Alembic antes de activarla; no modifica tablas bancarias ni aplica RLS automáticamente. El adaptador no restaura por sí mismo MemoryStore al reiniciar.

Intentos sin autenticación se devuelven como diagnósticos, no se guardan como turnos de un usuario; su auditoría de seguridad necesita un destino servidor separado. Los CSV, PDFs y datos originales permanecen locales. Habilitar inferencia autoriza técnicamente el envío del contexto de este flujo, no cargas masivas del dataset.

## Errores y verificación

Cada llamada conserva `trace_id`, etapa, tipo, archivo/función/línea y códigos HTTP o SQLSTATE cuando existen. Los errores se imprimen como JSON y aparecen en `persistence.events`; los usuarios reciben un mensaje ES/EN/PT sin secretos. No se imprimen cadenas de conexión ni cuerpos de error externos. No hay reintentos automáticos ni fallback que oculte fallos.

| Error/etapa | Causa y respuesta |
| --- | --- |
| `MISSING_DATABASE_URL`, conexión PostgreSQL/SQLSTATE | Configuración, red o esquema; detener antes de recuperar |
| `SESSION_REQUIRED`, `UNAUTHORIZED`, `CONVERSATION_ACCESS` | Sesión/rol/titular; detener sin enviar datos al modelo |
| `EXTERNAL_DISABLED`, `MISSING_API_KEY`, HTTP 401/403/429/5xx, timeout | Activación, proveedor, cuota o red; detener, no repetir automáticamente |
| `JEV_*`, `LLM_INCOMPLETE`, `LLM_REFUSAL`, validación JSON | Respuesta incompatible/incompleta; detener y conservar traza |
| `UNSUPPORTED_EXTRACTION`, `INVENTED_ID`, `INVALID_PERIOD` | Dato propuesto sin respaldo/formato válido; detener |
| `ROW_LIMIT`, `PAYLOAD_LIMIT`, `CONVERSATION_LIMIT`, `CALL_BUDGET` | Límite explícito; acotar/reiniciar solicitud, no truncar datos silenciosamente |
| `INVALID_CITATION`, `CITATION_MISMATCH`, `FORBIDDEN_OPERATION` | Salida LLM incompatible; no mostrarla como respuesta válida |
| `IDEMPOTENCY_CONFLICT`, `PERSISTENCE_*` | Reuso de ID, orden/versión o permisos de persistencia; detener y revisar |

## Ejecutar test_config y test_orquestador

Ambos archivos utilizan `unittest`, incluido en Python. Son pruebas locales: **no requieren Docker, PostgreSQL, cookies, `.env` ni claves de API**. No llaman a Jev/OpenAI ni validan conectividad real. Necesitan las dependencias del paquete para resolver sus importaciones.

En PowerShell, preparar el entorno una vez:

```powershell
Set-Location "C:\Users\santi\Documents\Projects\nexqori\chat-agente"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si ya existe un entorno preparado, utilizar su intérprete; no hace falta recrearlo. Los comandos siguientes usan directamente el Python de `.venv`, sin activar scripts de PowerShell. Ejecutarlos desde `chat-agente` para que se encuentre `nexqori_chat`.

**Sólo configuración (`test_config.py`):**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_config.py" -v
```

Comprueba prioridad de URL explícita, URL existente frente a componentes, defaults de Compose, codificación de contraseñas, host/puerto independiente y errores de configuración. No comprueba que el puerto esté abierto ni que la contraseña real sea correcta.

**Sólo coordinador (`test_orquestador.py`):**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_orquestador.py" -v
```

Usa `FakeRepository` y `FakeProviders` para comprobar bloqueo de reclamos, aclaraciones, tres respuestas no entendidas, placeholders, idempotencia y autenticación. No verifica la calidad de clasificación ni respuestas de modelos reales.

**Ambos archivos:**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

`-v` muestra cada caso. El resumen `OK` indica que las comprobaciones pasaron; `FAIL` señala una aserción incumplida y `ERROR` una excepción inesperada. La prueba de sesión inválida puede imprimir una traza JSON de error deliberada: evaluar el resultado final de `unittest`, no sólo esa línea. Si aparece `ModuleNotFoundError`, verificar el directorio actual y que las dependencias se instalaron con el mismo intérprete utilizado para probar.

**Estas pruebas no se ejecutaron durante esta edición.** La validación de autoría fue estática. Las verificaciones de citas/esquema no demuestran que toda afirmación natural sea correcta; evaluar calidad y seguridad offline y luego en shadow antes de integrar.

Fuentes: [skill TypeSafe](C:/Users/santi/.codex/skills/typesafe-ai/SKILL.md), [API TypeSafe](https://docs.typesafe.ai/api), [Choice](https://docs.typesafe.ai/primitives/choice), [clasificación jerárquica](https://docs.typesafe.ai/cookbooks/hierarchical_classification), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna). Disponibilidad de modelos/credenciales y ejecución real pendientes de validación autorizada.
