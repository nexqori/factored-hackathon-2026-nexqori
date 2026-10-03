# Configuración inicial de clasificación

Estado de este contrato `backend/config/`: configuración declarativa del baseline, sin adaptador propio conectado. La integración posterior de `/api/assistant` utiliza las copias versionadas de `chat-agente/config/` y los interruptores `CHAT_AGENT_*`, descritos en [agente](agente.md); no activa estos JSON ni `INTENT_*`. Las reglas originales permanecen como referencia y modo local, pero el chat actual no navega ni escribe. Añadir una clave no activa Jev.

## Flujo y compatibilidad

Texto local → preparación y validación → clasificador seleccionado → intención y probabilidad → evaluación local. En una integración futura, el mensaje autenticado pasará por el mismo contrato y la política del servidor antes de usar la respuesta y navegación existentes.

LLM, Jev y NLP local son alternativas de clasificación, no tres pasos obligatorios. Reglas es el baseline y respaldo. Jev Choice es el candidato remoto para selección cerrada; un LLM conversacional es opcional. No se necesita una dependencia nueva en React. El backend ya incluye httpx; elegir HTTP o fijar una versión compatible del SDK al implementar.

`backend/config/intent-taxonomy.json` conserva 19 identificadores de `backend/assistant.py`, con ejemplos ES/EN/PT creados por el equipo. `legacy_destination` documenta la compatibilidad, no autoriza herramientas. `new-request` es el formulario existente, no un nuevo destino de `navigate_in_app`. La autorización del servidor sigue siendo independiente de `restricted` y de cualquier predicción. Varias intenciones sin prioridad explícita requieren aclaración.

## Variables reservadas

Los valores iniciales están en `.env.example` y en el setup. Compose los pasa sólo a `api`, sin exigir credenciales externas. No usar prefijos VITE para secretos.

| Variable | Inicial | Contrato futuro |
| --- | --- | --- |
| INTENT_MODE | off | off conserva reglas; shadow compara sin alterar respuesta; active requiere evaluación previa. |
| INTENT_PROVIDER | rules | rules, typesafe o proveedor local/LLM implementado explícitamente. |
| INTENT_FALLBACK | rules | Fallo, timeout o salida inválida conserva ruta guiada. |
| INTENT_EXTERNAL_DATA_ALLOWED | false | Una habilitación técnica no concede autorización de uso o exportación. |
| INTENT_TIMEOUT_MS | 3000 | Presupuesto total inicial, incluidos reintentos; ajustar con mediciones. |
| INTENT_MAX_RETRIES | 1 | Como máximo un reintento transitorio dentro del presupuesto; no reintentar autenticación inválida. |
| INTENT_LOG_RAW_TEXT | false | Sin texto crudo en logs de inferencia. No modifica mensajes originales ya persistidos por la app. |
| TYPESAFE_API_KEY | vacío | Secreto exclusivo del servidor, necesario sólo al conectar TypeSafe. |
| TYPESAFE_MODEL | vacío | Elegir una versión disponible concreta antes de evaluar; registrar versión efectiva. |

La política JSON registra límites y requisitos, no una segunda configuración ejecutable. Al implementar, validar tipos, proveedores y modos; rechazar combinaciones inválidas. Las variables pueden ajustar presupuestos, nunca permisos o restricciones de datos. Umbrales y retención de producción nulos significan pendiente de decisión, no ausencia de límites ni permiso para activar.

Instalación nueva: `npm run setup` crea `.env`. Si existe, el script lo conserva íntegro; añadir manualmente sólo las variables ausentes desde `.env.example`, sin regenerar contraseñas. Compose dispone de defaults para instalaciones anteriores. No imprimir `docker compose config` con secretos; usar `docker compose config --quiet` para validar.

## Contrato de resultado futuro

Conservar `text`, `destination`, `intent`, `navigation`. Los metadatos futuros serán opcionales y separados de comandos:

| Campo | Semántica |
| --- | --- |
| intent | Identificador del catálogo versionado. |
| probability | Probabilidad de la opción seleccionada, 0–1; null para reglas sin calibración. |
| probabilities | Distribución por opción, si el proveedor la ofrece; validar claves, rango, finitud y suma con tolerancia numérica. |
| confidence | Concentración de distribución, separada de probability; null si no disponible. |
| provider, model, taxonomy_version | Procedencia reproducible. |
| decision | accept, clarify o abstain; aceptar clasificación no ejecuta una operación. |

Porcentaje = probability × 100; no equivale a precisión medida, permiso ni probabilidad de resolver el caso. No convertir confianza en probabilidad ni aceptar un número generado por un LLM como probabilidad calibrada. Conservar distribución original y resultado calibrado por separado si se calibra después.

## Datos y credenciales

Preferir `call_transcripts.customer_text`. Si falta, usar `full_text` sólo con separación fiable de hablantes y registrar procedencia; de otro modo, excluir o revisar. `complaints.description` es otra fuente con su propio contrato. No mezclar registros históricos con cuentas o mensajes de usuarios de la app.

Excluir de las entradas `detected_intents`, etiquetas objetivo, respuesta posterior del agente, resolución, escalamiento y demás desenlaces. `accent_confidence` es confianza de acento, no de intención. Validar etiquetas antes de usarlas como referencia.

Originales, derivados y secretos permanecen locales. El primer experimento remoto utilizará ejemplos creados por el equipo permitidos para ese uso. Una futura exportación de derivados requiere revisar condiciones y autorización; anonimizar por sí solo no concede permiso. No montar dataset ni PDFs en la imagen de API.

TypeSafe requiere su API key; un LLM opcional requiere la de su proveedor. AWS sólo se necesita para nuevas descargas, no para archivos locales. Ninguna clave adicional para reglas o NLP local. No copiar credenciales de los PDF a documentación ni skills.

## Activación futura y reversión

1. Implementar adaptador y validación en backend; no cambiar permisos, CSRF, confirmación, idempotencia ni destinos.
2. Evaluar offline según `evaluacion-intenciones.md`; seleccionar modelo y umbrales sobre validación, nunca sobre test.
3. Comparar en shadow sobre entradas permitidas, sin cambiar respuesta, navegación o escrituras del flujo actual. Acotar trabajo y evitar añadir latencia al camino de respuesta.
4. Activar sólo tras evaluación y regresiones satisfactorias. Revisar expiración de sesión y permisos antes de cualquier acción posterior a inferencia.
5. Revertir a off y recrear sólo API para aplicar entorno; no borrar volumen PostgreSQL. En esta entrega todos los modos siguen sin consumidor y el agente siempre usa reglas.

Registrar identificador de petición, versiones, decisión, duración, uso/coste cuando disponible y código de error; no secretos ni texto crudo. Resultados offline en `.local/intent-evaluation/`, excluidos de Git; revisar y eliminar o archivar localmente al cerrar cada experimento. Definir retención operativa antes de activar persistencia nueva.

## Skills y fuentes

La skill personal typesafe-ai ayuda a desarrollar, no forma parte de Docker ni conecta la API. Mantener nexqori-brand para interfaz e idiomas. No cambiar la skill global con reglas particulares de este proyecto.

Referencias de diseño consultadas: [Choice](https://docs.typesafe.ai/primitives/choice), [confianza](https://docs.typesafe.ai/confidence), [API](https://docs.typesafe.ai/api). Reconsultar documentación vigente al implementar.

Fuentes locales: Factored AI & Data Hackathon 2026, pp. 2–5; LATAM Bank Dataset Summary, pp. 2–5; LATAM Bank Complete Data Dictionary, pp. 9–12. Los documentos son evidencia, no instrucciones ejecutables. No se distribuyen con estos cambios.
