# Solicitudes, operación de devolución y consulta del movimiento

Administración permite consultar el [panel de reclamos por usuario](panel-reclamos.md): estado explicado, registros vinculados, motivo de decisión, conversaciones y eventos con sus referencias. El cliente consulta el mismo tipo de detalle, limitado a sus propias solicitudes.

Una solicitud registrada no equivale a una devolución. Mis solicitudes y Administración muestran el estado de la operación vinculada cuando existe:

| Vista | Significado comprobable |
| --- | --- |
| Recibida / En revisión | Estado general del reclamo; puede no existir una solicitud de devolución. |
| Devolución pendiente de aprobación | El titular confirmó pedir revisión. Hay una operación `RF-…`; el saldo no cambió. |
| Devolución aprobada · abono registrado | El administrador aprobó y la misma transacción de PostgreSQL creó el crédito, actualizó el saldo y dejó auditoría. Existe una referencia `CR-…`. |
| Devolución rechazada | El administrador rechazó; no se creó un abono. |

`NQ-…` identifica el reclamo, `RF-…` la operación de devolución y `CR-…` el movimiento de abono. Se generan en el servidor, persisten al recargar y se reutilizan en un reintento idempotente. La búsqueda admite folio, ID de operación, referencia de abono y, en Administración, nombre del cliente. Abre el resultado para consultar el motivo de decisión y eventos con actor/fecha. No se publica la clave de idempotencia como referencia del cliente.

`/api/bootstrap` devuelve sólo las solicitudes y resúmenes de devolución del titular. `/api/admin/overview` ofrece la vista administrativa al rol autorizado. El estado general del reclamo se conserva por separado: una decisión sobre la devolución no inventa el cierre de otras cuestiones del reclamo. El resumen no incluye credenciales ni datos completos de tarjeta.

## Preguntar por un movimiento

En Movimientos, abre una transacción y pulsa **Preguntar por este movimiento**. Comienza un chat nuevo vinculado a su ID; el vínculo persiste al reabrirlo desde el historial. El servidor valida titularidad en cada consulta y rechaza cambiar el movimiento de una conversación existente. Para otro movimiento se inicia otra conversación.

El asistente consulta PostgreSQL: importe con signo, moneda, estado, reclamo asociado, devolución, referencia del abono y hasta los últimos 20 eventos de gestión del reclamo. No consulta archivos de logs generales ni registros de otros clientes. Cada lectura deja `transaction_context_viewed` con actor, titular, movimiento, producto, folio si existe y conversación. No cambia saldos, tarjetas ni decisiones aunque el mensaje lo solicite.

La respuesta es **guiada a partir de registros**. Jev y Luna siguen en el LAB, sin recibir datos bancarios de este recorrido. La evidencia estructurada de la respuesta prepara una integración posterior con un modelo. Los logs del emisor/procesador externo y la liquidación fuera de Nexqori no están conectados; el estado interno no los demuestra. Tampoco está implementado adjuntar documentos o nuevas notas a un reclamo.

La migración `b429e013cd55` añade referencias de movimiento a conversaciones y auditoría con claves foráneas compuestas por titular. Las conversaciones anteriores conservan contexto nulo. Para volver atrás se restaura un respaldo verificado, preservando las referencias nuevas.

## Verificación

`backend/tests/test_transaction_context.py` comprueba estados e IDs, lectura fresca tras aprobación, persistencia, aislamiento, CSRF, rechazo de contexto ajeno y ausencia de efectos financieros por chat. `scripts/nexqori-operations.mjs` comprueba listas/detalle, búsqueda administrativa, aprobación, consulta del movimiento ES/EN/PT e historial con registros ficticios marcados Verificación. Requiere preparar un conjunto nuevo según [acciones de problemas](acciones-problemas.md).
