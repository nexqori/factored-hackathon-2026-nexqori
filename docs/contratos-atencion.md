# Procedimientos y contratos de atención — propuesta v1

Fecha de verificación: 29 de septiembre de 2026. Rama `bryan`.

## Qué exige el hackathon

Los originales locales `Datathon_2026_Kickoff.pdf` (pp. 12–13) requieren contratos de esquema estrictos, preparación reproducible, etiquetas válidas y evaluación reservada. `Factored AI & Data Hackathon 2026 (1).pdf` (pp. 3 y 5) pide contratos, calidad, procedencia y frescura de datos; acepta herramientas bancarias de prueba si se documentan sus contratos y límites. También exige permisos en el servicio y una identidad autenticada. No proporciona una plantilla de procedimiento por reclamo. Los originales permanecen fuera de Git.

Aquí distinguimos **contrato de datos** (qué campos son fiables), **contrato de herramienta** (entrada, permisos, salida y errores) y **procedimiento** (orden y condiciones para usar herramientas). La tabla siguiente es una propuesta de Nexqori, no una política entregada por el organizador.

## Referencias bancarias

- [BBVA México: aclaraciones por cargos no reconocidos, mal aplicados o duplicados](https://www.bbva.com/es/mx/como-levantar-la-aclaracion-de-un-cargo-no-reconocido-mal-aplicado-o-duplicado-en-tarjeta-de-credito/): referencia del recorrido desde el movimiento a la aclaración; publicación histórica, no fuente de plazos vigentes.
- [Santander México: centro de ayuda de aclaraciones](https://www.santander.com.mx/personas/informacion-y-ayuda/centro-de-ayuda/aclaraciones/): distingue motivos y documentación; permite consultar aclaraciones desde la tarjeta y conservar el folio.
- [BBVA: consulta de tarjeta digital](https://www.bbva.mx/educacion-financiera/banca-digital/como-se-genera-una-tarjeta-digital.html): número, vencimiento y CVV consultables en la app.

Estas referencias sustentan patrones de atención. Nexqori no hereda sus convenios, decisiones, plazos legales ni reglas de reembolso. Los controles técnicos y los nombres de herramientas siguientes son diseño propio. Un error de pantalla no demuestra que un pago falló.

## Tabla de procedimientos de problemas

Todas las filas parten de sesión vigente y datos del titular. El modelo identifica la necesidad; el servidor valida cada lectura o escritura.

| Caso / intención | Evidencia mínima y pasos | Resultado permitido | Contrato / disponibilidad |
|---|---|---|---|
| Cargo no reconocido (`unrecognized-charge`) | Seleccionar movimiento propio → consultar importe, fecha, comercio y estado → preguntar qué no reconoce y si hay contexto de suscripción/adicional → separar hechos de hipótesis → revisar y confirmar solicitud. | Folio de aclaración recibida. Si falta el movimiento, pedirlo; si hay riesgo, orientar a atención. No afirmar fraude ni una operación antes de recibir su comprobante. | Consulta propia + `POST /api/services/unrecognized-charge/requests`, ya disponible como registro. Bloqueo y devolución con revisión: disponibles en la base local; investigación de autenticación/red de pagos y conexión con emisor pendientes. |
| Importe distinto o duplicado (`incorrect-charge`) | Identificar cargo(s) propios → recoger importe esperado y comprobante/referencia → comparar comercio, moneda, fecha y estado → distinguir dos cargos asentados de una retención → confirmar reclamo. | Solicitud de revisión con diferencias y evidencia. Igual importe/comercio no prueba duplicación. | `POST /api/services/incorrect-charge/requests` registra; devolución completa con revisión administrativa disponible; comparación avanzada y adjuntos no implementados. El contrato actual admite un movimiento, no dos: conservar el segundo como referencia declarada hasta ampliar el esquema. |
| Pago pendiente, rechazado o resultado incierto (`payment-status`) | Consultar movimiento propio y referencia → verificar estado en fuente transaccional → si existen, consultar intento y liquidación con ID de correlación → aclarar si hubo cargo → resolver contradicciones antes de sugerir reintento. | Mostrar estado registrado o abrir revisión. Nunca recomendar pagar de nuevo sólo porque la app mostró un error. | `POST /api/services/payment-status/requests` disponible. Consulta de intentos/logs bancarios correlacionados: pendiente; `digital_events` no la sustituye. |
| Error de app (`app-support`) | Recoger pantalla, acción, hora, versión/canal y mensaje no sensible → determinar si involucra dinero → si lo involucra, pasar por estado de pago → registrar incidencia con pasos reproducibles. | Incidencia recibida o pregunta concreta. Nunca solicitar PIN, CVV, contraseña ni OTP en conversación. | `POST /api/services/app-support/requests` disponible. Diagnóstico técnico causal y telemetría del banco: no conectados. |
| Seguimiento de reclamo (`request-status`, consulta) | Pedir/seleccionar folio → validar titular → recuperar estado e historial → separar información confirmada de pendientes → resumir siguiente paso y fecha sólo si una fuente la aporta. | Estado real del folio y pendientes; derivación revisable si procede. No crear otro reclamo por defecto. | Disponible en la taxonomía interactiva de 24 etiquetas desde el 30/09: `read-request-status` consulta folio/devolución propios con sesión y auditoría. El LAB propone esa lectura sin ejecutarla. El benchmark congelado conserva 23 etiquetas. `POST /api/requests/{id}/handoff` registra derivación local, sin asignar especialista. |
| Atención en sucursal (`branch-support`) | Identificar lugar/canal, fecha aproximada, servicio y relato → comprobar si hay operación monetaria asociada → registrar y entregar folio. | Solicitud recibida; no atribuir conducta al empleado ni inventar una visita enlazada. | `POST /api/services/branch-support/requests` disponible; agenda/visitas/sucursal operativa no conectadas. |
| Calidad del servicio (`service-feedback`) | Preguntar experiencia, canal y resultado buscado → si existe reclamo, recuperar folio antes de duplicar → registrar opinión o reclamo según elección explícita. | Folio y resumen de lo registrado. | `POST /api/services/service-feedback/requests` disponible; evaluación de calidad no equivale a compensación aprobada. |

[Bloqueo y devolución con revisión](acciones-problemas.md) tienen efectos persistentes locales. La conexión a emisor, investigación externa y liquidación siguen pendientes. No se permite devolver un cargo sólo por su clasificación: el titular lo solicita y un administrador decide tras revisar evidencia.

## Consultas: recorrido independiente

Saldo, movimientos, tarjetas y consultas de productos no activan contratos de problemas ni instrucciones de reclamos. El LAB devuelve su ruta separada; no llama a Luna dentro del recorrido de problemas para estas intenciones. Consultar tarjetas usa `GET /api/cards` y, con contraseña, `POST /api/cards/{id}/reveal`; nunca transmite esos datos al LAB. El benchmark conserva estas categorías para medir si el modelo distingue consultas de problemas.

## Contrato común de una herramienta futura

Ejemplo de diseño para `investigate_transaction.v1`, **todavía no implementado**:

```json
{
  "input": {"transaction_id": "TX-1002", "question": "recognition"},
  "server_context": {"authenticated_user_id": "from_session", "trace_id": "server_generated"},
  "output": {
    "status": "needs_context",
    "verified_facts": [{"field": "transaction.status", "value": "completed", "source": "transactions", "record_id": "TX-1002", "observed_at": "2026-09-29T22:00:00-05:00"}],
    "missing_fields": ["customer_recognition"],
    "allowed_next_steps": ["ask_customer", "prepare_claim"],
    "executed_actions": []
  }
}
```

- Esquema versionado y campos extra rechazados. La identidad procede de sesión, jamás de una respuesta del modelo o de un ID escrito en el chat.
- Lectura: comprobar titularidad, fuente, fecha, consistencia y vínculo verificable. `not_found` no revela si existe un registro ajeno.
- Escritura: permiso específico, formulario revisable, confirmación vinculada a los datos concretos, clave de idempotencia y comprobante persistido. No basta un `confirmed=true` generado por IA; lo envía la acción explícita del usuario en el formulario autenticado.
- Estados propuestos: `ready`, `needs_context`, `inconsistent_evidence`, `unavailable`, `received`, `in_review`. El contrato local de acciones usa `blocked` para tarjetas y `pending`/`approved`/`rejected` para devoluciones, con comprobante persistido. No atribuir estos estados a un emisor externo.
- Errores: sesión vencida, acceso denegado, esquema inválido, registro ausente, conflicto idempotente, fuente no disponible y límite de frecuencia. Respuestas sin datos de otro cliente ni secretos.
- Trazabilidad: intención, versión del contrato/política, IDs de evidencia, decisión, confirmación y resultado. Nunca PAN completo, CVV, contraseña ni razonamiento interno del modelo.

## Condición «¿hay evidencia suficiente?» del diagrama

Es una comprobación por procedimiento, no un porcentaje de intención: titularidad verificada + campos mínimos presentes + fuentes identificadas/actualizadas + estados compatibles + política aplicable. Una pregunta específica puede completar información declarativa; no reemplaza una fuente bancaria ausente. Si faltan datos, preguntar; ante contradicción o servicio indisponible, detener la acción y preparar revisión con evidencia y pendientes.

Jev y Luna deben recibir la misma conversación/categorías y producir lecturas independientes. Acuerdo no prueba corrección: medir también errores compartidos. Con desacuerdo, salida inválida o información insuficiente no se elige silenciosamente un ganador. La propuesta sólo navega o prepara un formulario; permisos, confirmación y ejecución siguen en el banco.

## Calidad de los datos y prueba siguiente

El EDA agrega 12.297 cargos no reconocidos, 12.194 cobros indebidos, 12.128 problemas de app, 11.892 de sucursal y 11.886 de calidad sobre 67.095 casos. Son datos sintéticos del organizador, no conversaciones auténticas ni tasas de resolución. [Evidencia agregada](../notebooks/servicios_nexqori/catalog_evidence.json).

Los enlaces caso–producto no son confiables: 44.570/44.570 referencias comparables apuntan a otro titular. Eventos–producto: 1.094.226/1.094.242 discrepancias. No cruzar por cercanía temporal para completar evidencia. Transacción–producto–cliente sí concuerda en 4.425.008 filas. Ningún caso tiene `origin_interaction_id` utilizable. Por ello, no importar esos vínculos a la base operativa.

La próxima evaluación debe cubrir reconocimiento, importe, estado de pago y seguimiento, con casos nuevos reservados ES/EN/PT, cambios de intención, múltiples necesidades, titular ajeno, fuente caída, evidencia contradictoria y petición de datos sensibles. Medir clasificación por separado de resolución, llamadas/coste/latencia, derivaciones y acciones inseguras. Las reglas locales aprobadas por Bryan exigen revisión administrativa de devoluciones; automatizar una decisión por IA sigue fuera de alcance.
