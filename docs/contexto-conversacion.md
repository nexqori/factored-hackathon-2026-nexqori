# Continuidad del chat bancario

Actualizado el 2 de octubre de 2026, America/Lima.

El chat conserva el relato del cliente, el contrato del problema y las preguntas pendientes entre mensajes. Consultar el historial no ejecuta modelos. Los subagentes usados para revisar esta mejora pertenecen a la sesión de Codex; no se añadió un sistema de subagentes al aplicativo.

## Qué se corrigió

Había tres diferencias entre lo que veía el cliente y el estado utilizado al continuar:

- Una consulta mostraba una respuesta bancaria, pero el historial del intérprete guardaba la respuesta genérica del editor. La siguiente clasificación no conocía el tema de la respuesta que acababa de ver el cliente.
- Al completar un problema y quedar pendiente de revisión, el siguiente mensaje reconstruía el flujo desde el inicio. Una corrección podía perder el contrato seleccionado o provocar otra clasificación.
- Mientras había una pregunta pendiente, el flujo interpretaba incluso un cambio explícito de tema como una respuesta a esa pregunta.

Ahora cada consulta conserva una descripción segura de su tema. Una propuesta de movimiento conserva la pregunta de confirmación, sin copiar el movimiento al proveedor. Las correcciones de un problema listo para revisión vuelven a **Contexto** con el mismo contrato. Una evaluación de contexto que falló puede retomarse con un mensaje nuevo sin borrar lo ya declarado.

## Continuación y cambio de tema

| Situación | Comportamiento |
| --- | --- |
| Respuesta a una pregunta pendiente | Conserva clasificación y contrato; vuelve a Contexto. |
| Corrección tras reunir los datos | Revisa otra vez el contexto con el relato anterior y la corrección; no clasifica de nuevo. |
| «Ahora quiero consultar mi saldo» | Interrumpe la pregunta anterior y Jev clasifica la nueva petición. |
| Consulta seguida de «¿puedo tenerlo en PDF?» | La clasificación recibe el tema de la consulta anterior, junto con el texto del cliente; la generación requiere los parámetros y controles del banco. |
| Confirmación de un movimiento propuesto | Vincula sólo la referencia propia validada por el servidor; continúa el contrato pendiente. |
| Proveedor de contexto no disponible | Conserva contrato y mensajes. Un mensaje nuevo permite reintentar; repetir la misma petición idempotente recupera su resultado anterior. |
| Reclamo ya registrado | Los mensajes siguen en el mismo expediente. Para otro reclamo se inicia una conversación nueva. |

Los cambios de tema se detectan mediante expresiones explícitas en español, inglés y portugués. Esa detección sólo decide si hace falta clasificar de nuevo; no selecciona un servicio ni autoriza una acción. «Esperaba 100», «sí, es éste» o «ahora recuerdo la fecha» siguen siendo aclaraciones. Una referencia distinta de la ya vinculada requiere una conversación nueva, como antes.

## Dos historiales con funciones distintas

**Historial del cliente:** los mensajes completos y las respuestas que vio el cliente permanecen en PostgreSQL, asociados al titular y a la conversación. Puede incluir resultados bancarios que el cliente tiene permiso para consultar.

**Historial del proveedor:** contiene el texto escrito por el cliente y respuestas seguras del intérprete. Para consultas y sugerencias contiene el tema o la pregunta pendiente, sin incorporar importes, comercios, referencias, tarjetas, registros o credenciales obtenidos del banco. Los identificadores o cifras que el propio cliente escribe sí forman parte de su mensaje.

Al iniciar otra ejecución en una conversación larga, el historial del proveedor conserva la apertura y los turnos recientes, hasta 28 mensajes anteriores. No se genera un resumen mediante un modelo ni se copia la tabla de mensajes visibles. Las aclaraciones de un problema mantienen el límite del intérprete; completar un turno no lo reinicia. El historial completo sigue disponible en la base.

La continuidad permite mantener el tema y el contrato. No convierte una clasificación en autorización, no ejecuta pagos ni garantiza que el modelo interprete correctamente cualquier referencia ambigua. Las respuestas bancarias siguen usando las herramientas de lectura y las plantillas permitidas; no se envían registros a un modelo para producir respuestas libres.

## Prueba repetible sin claves

```powershell
.venv-app/Scripts/python.exe -m pytest backend/tests/test_chat_context.py backend/tests/test_workflow_chat.py backend/tests/test_transaction_suggestions.py -q
```

Las pruebas usan la API y el intérprete reales con SQLite aislado y proveedores controlados. Cubren conversaciones de tres turnos en ES/EN/PT, corrección de importe esperado, consulta y PDF, cambio explícito de tema, confirmación de movimiento, recuperación tras fallo, apertura conservada y ausencia de registros bancarios en los mensajes enviados a proveedores. Verifican también que no cambien saldos, movimientos ni solicitudes.

Implementación: [adaptador del chat](../backend/workflow_chat.py), [memoria segura](../backend/conversation_context.py) y [pruebas de continuidad](../backend/tests/test_chat_context.py). La aceptación visual y las pruebas reales de proveedores siguen los comandos de la [guía de chat y pagos](chat-bancario-y-pagos.md).
