# Motor de atención con LangGraph

Desde esta integración, el chat bancario y el editor ejecutan el flujo maestro con **LangGraph 1.2.12**. React Flow conserva la edición visual. Jev clasifica y Luna extrae contexto; los contratos, herramientas permitidas y confirmaciones siguen en la aplicación.

## Qué ejecuta

Cada bloque guardado se convierte en un nodo de `StateGraph`. Sus conexiones se convierten en rutas condicionales. LangGraph planifica los bloques desde el siguiente nodo autorizado por el servidor. El mismo grafo atiende consultas y las seis familias de problemas.

| Control | Comportamiento |
| --- | --- |
| Seleccionar un bloque | Consulta el último resultado; no ejecuta proveedores. |
| Paso a paso | Ejecuta exactamente un bloque y guarda el siguiente. |
| Flujo completo | Continúa hasta respuesta, pregunta o límite de 40 bloques. |
| Preguntar | Espera respuesta real o una nueva referencia propia; después vuelve a Contexto. |
| Repetir un bloque | Usa la función de repetición explícita existente, conservando el original. |
| Fallo inesperado | Marca la ejecución como interrumpida. No repite automáticamente el bloque. |

Las operaciones financieras no se añaden como herramientas autónomas de LangGraph. Pagar y transferir mantienen revisión, confirmación, idempotencia, titularidad y transacción bancaria. Registrar un reclamo exige confirmación y una devolución necesita aprobación administrativa. El editor sigue mostrando qué se activaría.

## Persistencia y compatibilidad

La persistencia pertenece al anfitrión: PostgreSQL en el banco y archivos JSON locales en el editor. Se conserva el esquema existente de conversaciones, entradas por bloque, versiones y siguiente nodo. Los checkpoints previos pueden continuar sin volver al inicio ni repetir la clasificación.

No se añade otro almacén `PostgresSaver`: el banco debe guardar resultado, mensajes, auditoría y turno idempotente en la misma transacción. Un segundo almacén tendría otro momento de commit. LangGraph se compila de nuevo cuando es necesario y se reanuda desde el estado autenticado del anfitrión. No se utiliza `MemorySaver` como persistencia entre peticiones.

La caché guarda sólo IDs y conexiones. El lector del titular, los callbacks y el estado se suministran en cada invocación. Las respuestas bancarias no se añaden al contexto de los modelos. La exportación de trazas a LangSmith está desactivada dentro de esta ejecución, incluso si el proceso tiene tracing configurado. El editor conserva sus eventos filtrados y su JSON técnico; el cliente del banco conserva su vista de conversación.

Los resultados nuevos incluyen `runtime.name = langgraph` y su versión en el JSON del editor. Una ejecución antigua no ejecutada aún conserva la marca `legacy`; consultarla no cambia su historial.

El runtime no promete una única llamada externa ante todas las caídas. Si un proveedor respondió y el proceso cae antes de confirmar el turno PostgreSQL, un reintento puede consumir otra llamada. Las confirmaciones financieras e idempotencia bancaria no dependen de esa llamada.

## Actualizar y probar

1. Actualiza `main` y ejecuta `npm ci`.
2. Reconstruye el banco con `npm run docker:up`. No borres volúmenes.
3. Actualiza el entorno del editor con `pip install -r experiments/intent-lab/requirements.lock` y reinicia su servidor según [su guía](../experiments/intent-lab/README.md). Conserva `.local/intent-lab`.
4. Abre [el banco](http://localhost:5180) y [el editor](http://localhost:5190/?view=flows&mode=editor&lang=es).

Tres recorridos manuales:

1. **Consulta:** pregunta «¿Cuál es mi saldo?» y luego «Quiero el estado de cuenta en PDF». Elige cuenta y período. El documento debe aparecer en Mis solicitudes; no se registra un reclamo.
2. **Problema:** desde Movimientos, pregunta por un cobro y explica que el importe es incorrecto. Responde cuánto esperabas pagar. Debe conservar el contrato y pedir sólo lo pendiente. Revisa y confirma el reclamo para verlo en Mis reclamos.
3. **Editor:** inicia por pasos, selecciona otro bloque y vuelve al anterior. El resultado permanece. Continúa con Flujo completo. Cuando pregunte, responde y comprueba que retorna a Contexto sin repetir Jev.

Para probar evidencia de un pago que aún no termina, abre **Servicios → Teléfono**, busca el recibo por número y elige **Pendiente de procesamiento** antes de confirmar. El importe se descuenta una sola vez y el movimiento queda pendiente. Consulta su detalle y usa **Preguntar al asistente** para hablar del mismo movimiento. No se crea una solicitud por pagar: el reclamo sólo aparece después de revisarlo y confirmarlo en el chat. Este modo local no programa una fecha ni completa el pago automáticamente; consulta sus límites en la [guía de pagos](pagos-y-transferencias.md).

Comprobaciones repetibles (requieren los entornos de [inicio](../INICIO-EQUIPO.md)):

```powershell
.venv-app/Scripts/python.exe -m pytest backend/tests -q
$env:PYTHONPATH = "$PWD/experiments/intent-lab;$PWD"
.local/intent-lab-venv/Scripts/python.exe -m pytest experiments/intent-lab/tests -q
npm run test:lab:master
npm run test:lab:bank
npm run test:chat:flow
npm run test:payments
npm run test:payments:pending
npm run test:banking
npm run test:ui
npm run test:experience
```

Ejecuta las pruebas de navegador en serie. Crean registros de verificación persistentes y guardan evidencias privadas. Las pruebas controladas no consumen modelos. `npm run test:chat:live` sí usa los proveedores configurados; no confirma operaciones financieras.

## Implementación

- [Planificador LangGraph](../experiments/intent-lab/intent_lab/langgraph_runtime.py): compilación, rutas, límites y aislamiento de invocaciones.
- [Ejecución de bloques](../experiments/intent-lab/intent_lab/workflow_execution.py): contratos, preguntas, evidencias y checkpoint compatible.
- [Adaptador bancario](../backend/workflow_chat.py): sesión, contexto seguro y commit transaccional.
- [Referencia de LangGraph](https://docs.langchain.com/oss/python/langgraph/graph-api): API usada. Las dependencias transitivas están fijadas en los tres `requirements.lock` del banco, editor y Security Lab.

La voz sigue aplazada. Esta integración no activa micrófono, recaudadores ni liquidación externa.
