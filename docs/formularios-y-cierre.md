# Formularios y cierre de atención

Integra la contribución `araceli@38912ae` en el chat actual. Conserva NPS, CSAT, CES y sus métricas. Sustituye el temporizador de inactividad por el cierre del pitch: **resolución confirmada + ausencia de gestiones pendientes → 15 minutos**.

## Recorrido

1. Administración abre un expediente en **Reclamos → Resultado y opinión**, escribe la solución y confirma que no quedan gestiones pendientes. Para una consulta completada, el titular confirma desde **Chat → Detalles**.
2. El servidor valida titularidad, rol, confirmación y los registros disponibles. Rechaza pagos o devoluciones pendientes. Para pendientes externos, el administrador debe comprobarlos antes de marcar la confirmación; todavía no hay un sistema de tareas externo conectado.
3. Se guarda el plazo en PostgreSQL. El cliente puede elegir **Valorar la atención**, responder NPS/CSAT, añadir CES o comentario y **Guardar respuesta parcial**. No necesita completar nada para que se registre el resultado de la atención.
4. A los 15 minutos, el proceso de la API captura el resultado y la información disponible: enviada, parcial o sin respuesta. Revisa cada 30 segundos y recupera plazos vencidos tras reiniciar. Un cambio del expediente, nuevo mensaje de consulta o una gestión pendiente detiene el cierre.
5. El formulario sigue disponible después. Completarlo actualiza las métricas; no modifica la captura original del cierre. **Aún necesito ayuda** reabre la atención y deja auditoría.

El cierre afecta a la atención, no al estado contable del pago ni a la decisión de una devolución. No ejecuta pagos, bloqueos ni abonos. Los mensajes permanecen visibles. Las respuestas no se envían a modelos ni se aplica análisis automático de sentimientos.

## Datos y métricas

- `attention_reviews`: titular y referencia única a reclamo o conversación; resumen, persona que confirmó, plazo, estado, comparación de registros, respuestas y capturas de cada cierre.
- `chat_feedback`: contribución original de Araceli. Sólo respuestas enviadas alimentan las métricas nuevas. NPS = % de 9–10 menos % de 0–6; CSAT = % de 4–5; CES = promedio sobre 1–7. Una respuesta ausente es `null`, nunca una puntuación cero.
- Los formularios nuevos no miden duración de conversación/formulario. Los tiempos históricos siguen disponibles; los nuevos valores desconocidos se excluyen de las medias.
- El evento `attention_closed_by_timer` identifica al servidor como disparador y conserva quién autorizó el cierre. Fecha de cierre real y fecha prevista se distinguen.
- Migración `c84ab091fa22` une las ramas `b37d1f4c9a20` y `f5a306c829d1`; conserva las tablas existentes. Hacer respaldo antes de `alembic upgrade head`.

## Casos para el pitch

| Caso | Evidencia que mostrar | Resultado verificable |
|---|---|---|
| Camila: compra de 2.700 MXN frente a historial habitual de 600 | Detalle de tendencia y movimiento confirmado | Reclamo con resumen; bloqueo sólo por el recorrido confirmado con correo. Nunca afirmar devolución automática. |
| Camila: teléfono de 459 MXN frente a 299 | Recibo, estado pendiente y publicación controlada de tarifa | Distinguir aumento publicado de pago pendiente. No cerrar mientras el pago siga pendiente. Fuente de ejemplo, no tarifa real de una empresa. |
| Seguimiento y resolución de un reclamo | Conversación, documentos y decisión administrativa del mismo caso | Confirmación de solución, formulario parcial, cierre tras 15 minutos y respuesta posterior sin perder trazabilidad. |

Pruebas: `python -m pytest backend/tests/test_attention.py backend/tests/test_migrations.py -q`, `npm run test:attention`. Usan registros aislados y reloj controlado; no aceleran plazos de clientes ni consumen voz/LLM. La voz real requiere resolver primero el acceso al modelo. No se presenta el cierre de atención como resolución automática de un cargo.

Revisión GitHub de esta integración: no había PR abiertos ni rama remota de Santiago. Sus cambios pendientes requieren enlace o publicación para revisarlos; no se dan por integrados.
