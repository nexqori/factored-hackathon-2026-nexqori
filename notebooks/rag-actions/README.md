# RAG PostgreSQL, respuesta natural y CSV

`POSTGRES_RAG_ACTIONS_EXPERIMENT.ipynb` implementa el recorrido experimental: **texto + contexto/intención/evidencia revisados → reglas → PostgreSQL → información relacionada → GPT-6 Luna → respuesta en lenguaje natural → CSV**. Editado sin ejecutar: no se generaron respuestas ni resultados durante la autoría.

El RAG selecciona consultas parametrizadas y recupera productos, movimientos, solicitudes, relaciones solicitud–movimiento–producto, conversación reciente y reglas v1.1.0. Comprueba sesión y titularidad. No genera SQL con IA, no requiere pgvector ni modifica tablas de la app. Si faltan datos, pide aclaración; si se exceden límites, detiene el proceso para acotar la consulta. El historial usa los últimos cinco mensajes anteriores al corte y declara si existen anteriores.

El LLM redacta `answer` en lenguaje natural, con citas a los hechos. Se muestra ese texto directamente; ya no se limita a ordenar una plantilla. Ninguna respuesta autoriza ni ejecuta operaciones. Desconocido exige el mensaje del catálogo solicitando un nuevo requerimiento.

## Dependencias y credenciales

Instalación manual: `psycopg[binary]>=3.2,<4`, `httpx`, `python-dotenv`, `nbformat`, en un kernel Python/Jupyter. No hay instalación automática.

| Variable externa | Fixtures | Base real de la app |
| --- | --- | --- |
| `RAG_POSTGRES_DSN` | Base de investigación con permiso TEMP | Base Nexqori con rol de lectura mínimo |
| `OPENAI_API_KEY` | Necesaria para respuestas LLM | Necesaria para respuestas LLM |
| `NEXQORI_SESSION_TOKEN` | No necesaria | Sesión de cliente vigente |

Se lee `.env` de la raíz sin sobrescribir el entorno del proceso. No pegar secretos en celdas, CSV o Git. PostgreSQL de Compose no publica puerto al host: usar kernel en su red o una base accesible preparada. No se cambian Compose ni puertos. El rol real necesita SELECT sobre products, transactions, requests, messages, users y sessions; sin privilegios de escritura, superusuario ni BYPASSRLS.

## Activación mediante variables

Todos los interruptores se entregan en `False`. Editar la primera celda con `True`/`False` y reiniciar kernel al cambiar `MODE`. Elegir una sola ruta LLM.

| Variable | Un fixture + LLM | 30 fixtures + LLM | Un ejemplo real + LLM |
| --- | --- | --- | --- |
| `MODE` | `'fixtures'` | `'fixtures'` | `'app_readonly'` |
| `ALLOW_DB_CONNECTION` | `True` | `True` | `True` |
| `ALLOW_FIXTURE_SETUP` | `True` | `True` | `False` |
| `ALLOW_LLM_CALLS` | `True` | `True` | `True` |
| `ALLOW_CSV_WRITE` | `True` | `True` | `True` |
| `ALLOW_REAL_DATA_TO_LLM` | `False` | `False` | `True` |
| `RUN_DATABASE_TESTS` | Opcional `True` | Opcional `True` | `False` |
| `RUN_LLM_TEST` | `True` | `False` | `False` |
| `RUN_FIXTURE_BATCH` | `False` | `True` | `False` |
| `RUN_REAL_EXAMPLE` | `False` | `False` | `True`, un solo uso |

Sólo verificaciones RAG sin LLM: modo fixtures, conexión/setup/pruebas DB en `True`; llamadas LLM, CSV y las tres rutas LLM en `False`.

La ruta real con LLM está implementada a petición del usuario. Activarla permite enviar a OpenAI el mensaje, contexto revisado, ventana de conversación, datos propios recuperados y reglas del ejemplo seleccionado. No se envían credenciales ni SQL. Revisar los campos libres antes de activar el envío. Una clave por sí sola no activa esta ruta. No se importan ni exportan los archivos originales del organizador.

## Probar fixtures

1. Configurar entorno y la columna elegida de la tabla.
2. Para uno, seleccionar `FIXTURE_CASE_ID`, por defecto `'balance_account'`; para todos, usar `RUN_FIXTURE_BATCH=True`.
3. Cuando se decida ejecutar, correr las celdas en orden. Las tablas son TEMP y desaparecen al cerrar cada conexión. La suite DB opcional precede a las llamadas LLM.
4. Consultar la respuesta visible y el CSV indicado. El lote guarda una fila por caso y se detiene al primer fallo, conservando filas anteriores y la fila de error cuando es posible.

Los 30 casos cubren saldo positivo/cero/nulo, ahorro, tarjetas/cuentas/productos, fechas, historial vacío, movimientos completados/pendientes/rechazados, solicitudes recibidas/en revisión/derivadas, supervisión, humano, datos faltantes, desconocido ES/PT, correo no disponible, navegación, registro ajeno, inyección SQL y de instrucciones, acceso administrativo y preparación de revisión. Incluyen ES/PT y regresión EN. Cada caso contiene expectativas de registros, estados y algunos valores; no se envían al LLM.

## Probar un ejemplo real

1. Configurar la columna real y las tres variables externas.
2. Editar **un diccionario** `REAL_CONTEXT` en la última celda: mensaje, idioma, intención, acción, clase de evidencia, alcance y filtros revisados. El ejemplo consulta cuentas propias sin IDs ficticios. Actualizar `cutoff` al momento de la solicitud.
3. Ejecutar las definiciones y esa celda. `run_real_example(REAL_CONTEXT)` valida configuración/sesión, recupera datos, llama una vez al LLM y guarda una sola fila en un CSV nuevo.
4. `RUN_REAL_EXAMPLE` se pone en `False` antes de intentar el caso, incluso si falla. Otra consulta requiere reactivarlo manualmente. No se admiten listas ni lotes reales; un lock impide procesos simultáneos en el mismo kernel. No es un bloqueo distribuido entre kernels.

Intención y evidencia **no se infieren automáticamente desde el texto** aquí. Se aportan revisadas, con procedencia y valores para hechos semánticos. No se enlazan automáticamente los notebooks anteriores. El LLM no decide qué usuario consultar ni obtiene permisos mediante el mensaje. La base real usa el esquema de Nexqori, no los CSV históricos de `nexqori-dataset`.

## CSV y verificación

Ruta: `notebooks/rag-actions/private/results/`, excluida de Git. Nombres únicos `fixture_*.csv`, `fixtures_batch_*.csv`, `real_single_*.csv`. Se crean sólo al ejecutar con guardado habilitado.

Cada fila incluye:

- Ejecución/caso, modo, fecha, estado y duración.
- `context_json`: mensaje, intención, evidencia, filtros y hechos revisados.
- `rag_json`: hechos, relaciones, historial utilizado, reglas, preguntas, capacidades, versión/hash y trazas SQL con parámetros sin identidad cruda ni credenciales.
- `llm_request_json`: body exacto enviado, incluidas instrucciones, input, modelo, esquema y parámetros; sin headers de autorización.
- `llm_response_json`, `answer_json`, `answer_text`, modelo efectivo y uso reportado.
- `checks_json`, `error_json` y columnas vacías de revisión humana: exactitud, claridad, cumplimiento y notas.

Los campos estructurados son JSON dentro del CSV. Texto que pueda iniciar una fórmula se escapa en `answer_text`; `answer_text_escaped` lo indica y `answer_json` conserva el original. Credenciales, DSN y tokens no forman parte de la trazabilidad. Los CSV contienen información privada: no publicarlos.

La validación automática comprueba referencias y estructura, no toda la verdad semántica de la respuesta. Revisar importes/signos/moneda, estados, pertenencia, preguntas, claridad y ausencia de promesas de operaciones. `generated_structurally_valid` no equivale a caso resuelto ni a exactitud medida.

## Detención ante errores

Las entradas públicas se detienen ante fallos técnicos, incluidos autorización, conexión, API, límites, citas, CSV y visualización. Muestran etapa y diagnóstico controlado; para errores externos, tipo y HTTP/SQLSTATE cuando existen. No imprimen cuerpos privados ni secretos. No hay reintentos (`LLM_RETRIES=0`) ni fallback silencioso.

Una respuesta inválida se guarda como error junto con los insumos y no se muestra como válida. Si el guardado falla, también se detiene. `PROCESS_STOPPED=True` exige corregir la causa y reiniciar kernel; reejecutar configuración no borra el bloqueo ni repone presupuesto. Las pruebas negativas capturan sólo errores esperados; una comprobación incumplida detiene la suite. No configurar el ejecutor para continuar tras errores.

Fuentes API: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna). La disponibilidad del modelo para la cuenta se comprobará al ejecutar; no se sustituye silenciosamente.
