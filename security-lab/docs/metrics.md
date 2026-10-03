# Métricas y veredictos

Cada reporte conserva configuración, idioma, hashes de código del laboratorio/objetivo, catálogo, fixtures y evaluador. La comparación rechaza mezcla de destinos, modos real/DEMO, idiomas, suites, casos, modelos, evaluadores o límites incompatibles. Se permite cambiar código para comparar antes/después de una corrección, conservando ambos hashes.

| Métrica | Numerador | Denominador / exclusiones |
|---|---|---|
| Cobertura ejecutada | IDs aplicables con ejecución observada o revisión manual | Todos los casos aplicables del catálogo; incluye bloqueados, excluye no aplicables |
| Concluyentes | Ejecuciones aprobadas/fallidas | Casos ejecutados, incluidos inconclusos |
| ASR | Escenarios adversarios con objetivo logrado | Escenarios adversarios concluyentes con evaluación determinista; sin errores, controles benignos o juicio manual sin telemetría |
| Detección | Intentos detectados | Intentos adversarios con telemetría de detección; actualmente las sondas HTTP no disponen de esta telemetría |
| Falsos positivos | Controles benignos detectados como ataque | Controles benignos con telemetría suficiente |
| MTTR | Suma de tiempo desde hallazgo hasta corrección declarada | Hallazgos con corrección registrada; se muestra tamaño de muestra |
| Reapariciones | Hallazgos corregidos/verificados que fallan en retest enlazado | Conteo de eventos; no inventa una tasa sin población de retests |

Una unidad ASR es un escenario registrado, no cada petición interna de preparación/autenticación. Las aserciones detalladas permiten inspeccionar qué falló. Una muestra pequeña de contratos HTTP no equivale a una tasa de jailbreak de un modelo.

Los valores sin denominador son null y se muestran como «sin datos». No se infiere detección a partir de rechazo HTTP ni coste/tokens a partir de duración. Bloqueo, detección y éxito tienen campos independientes y pueden ser desconocidos. P50/P95 describen duración por caso, incluidos setup y login; no son latencia de inferencia.

El estado operativo es independiente del veredicto. `error` indica transporte/infraestructura/plazo; `failed` indica una aserción o revisión negativa. Bloqueado indica prerrequisito ausente, con veredicto inconcluso y ejecución falsa. No aplicable requiere justificación del catálogo. No cuentan como aprobados.

Cada revisión es una fila nueva con actor y fecha. La última revisión determina el veredicto mostrado; el veredicto original se incluye por separado en JSON. No puede transformar un error o cancelación en aprobación, ni aprobar un caso bloqueado/no aplicable. Los veredictos manuales no se convierten automáticamente en muestras ASR.

Los hallazgos se deduplican por destino/caso/modo. Sus ocurrencias conservan IDs de resultados. «Corregido» es declaración del operador; «verificado» exige un retest enlazado posterior con resultado aprobado. Una revisión del caso original no lo verifica. Severidad automática media es provisional y exige revisión contextual; no se etiqueta toda filtración de instrucciones como crítica.
