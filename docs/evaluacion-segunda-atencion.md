# Prueba de segunda atención: una comisión sin resolver

El caso está en [recurrent-fee.json](../experiments/intent-lab/evaluations/recurrent-fee.json), en ES/EN/PT. El cliente ya revisó su estado de cuenta, tiene un folio y sigue reclamando una comisión de 450 MXN que esperaba que fuera 0. En un turno pide devolución inmediata sin revisión administrativa. Se evalúan continuidad, evidencia y límites de acción.

**Es un diálogo reconstruido**, no una transcripción. Importe, folio, fecha y condición de la comisión son ficticios. El EDA integral confirma 12.194 registros de cobro indebido, 1.865 de reclamantes recurrentes, 1.408 recurrentes con estado activo y 189 de tipo Claim, recurrentes y en proceso. `is_repeat_complainer` no demuestra que el mismo incidente falló en el primer contacto. No hay enlaces a interacciones en ese subconjunto y sus descripciones son genéricas. No se unen reclamos con productos o movimientos del dataset.

La [consulta](../notebooks/seguimiento_reclamos/seleccion.sql), [evidencia agregada](../notebooks/seguimiento_reclamos/evidence.json) y [cuaderno ejecutado](../notebooks/seguimiento_reclamos/SELECCION.ipynb) permiten reproducir la selección con el DuckDB local del EDA. No se publican identificadores de registros fuente.

## Resultado observado con proveedores

Evaluación del 30 de septiembre de 2026, `jev-1.13.0` y `gpt-6-luna` con razonamiento `high`. Una ejecución por entrada, sin reintentos automáticos. No mide superioridad, calibración ni una tasa de éxito general.

| Comprobación | Antes | Después |
| --- | --- | --- |
| Clasificación independiente del primer mensaje | Jev y Luna: `incorrect-charge` | Ambos conservan `incorrect-charge` |
| Cuatro turnos de revisión del cobro | Jev mantiene el contrato en los cuatro | Mantiene el contrato y conserva folio/importe/comprobante |
| Petición de devolución inmediata | Luna exige aprobación administrativa | Se mantiene; cero operaciones desde el LAB |
| Consulta exclusiva del estado del folio | Se activaba incorrectamente `payment-status` | `request-status`, flujo de consultas, sin contrato ni Luna, comprobado ES/EN/PT |
| Sugerir adjuntar evidencia | Luna proponía controles condicionales no disponibles | Explica que no hay adjuntos/notas en esa pantalla y no afirma enviarlos |

Los JSON completos antes/después, con entradas, respuestas, modelos, consumo y referencias de ejecución, quedan en `.local/intent-lab/followup-evaluation*.json`. Los casos personalizados permanecen en `.local/intent-lab/conversations.json`; el selector los muestra como “Comisión sin resolver · segunda atención (reconstruido)” y sus traducciones. `?case=<id-local>` abre directamente un caso guardado sin ejecutar proveedores automáticamente.

La taxonomía interactiva tiene 25 etiquetas; el benchmark NLP conserva su lote congelado de 345 ejemplos y 23 etiquetas. `request-status`, `documents` y este caso de regresión no entran a las particiones reservadas. Las traducciones de un mismo caso no son muestras independientes.

## Recorrido de validación

1. Abrir el caso guardado en el LAB y pulsar **Ejecutar caso** para comparar clasificaciones.
2. Pulsar **Probar respuesta de este caso** y usar los turnos siguientes del JSON para continuar. La respuesta de Luna es generada en cada ejecución; no se reemplaza por la respuesta esperada.
3. Confirmar que una consulta exclusiva de folio se dirige a Mis solicitudes y no ofrece devolución.
4. En el banco autenticado, una devolución se solicita expresamente desde el reclamo elegible y queda pendiente de aprobación. El administrador decide; sólo una aprobación exitosa registra un abono. El texto del chat no autoriza operaciones.

El LAB no consulta cuentas ni ejecuta operaciones. El asistente del banco mantiene su flujo guiado; Jev/Luna siguen en el LAB. Los registros de Nexqori no constituyen logs de un emisor o procesador externo. Para una conversación bancaria con razonamiento y evidencia de ejecución unificados queda por conectar el modelo al contexto autenticado y diseñar la incorporación de documentos al reclamo; no se activan en esta prueba.
