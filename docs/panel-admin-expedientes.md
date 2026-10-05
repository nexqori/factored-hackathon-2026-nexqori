# Expediente administrativo

Acceso local: http://localhost:5180/admin/complaints con una cuenta de administración.

1. El cliente registra y confirma un reclamo desde su chat. El reclamo conserva su identificador y movimiento, si existe.
2. En administración, pulsa **Actualizar casos**, filtra por cliente y selecciona el reclamo.
3. **Resumen** muestra el relato registrado, importe, referencia, estado y siguiente paso. Una devolución pendiente requiere una decisión distinta de la revisión del reclamo.
4. **Conversaciones** permite leer mensajes originales y consultar la evaluación del asistente de forma desplegable. Una conversación sobre el mismo movimiento aporta contexto; no demuestra por sí sola que todos sus mensajes correspondan al reclamo.
5. **Documentos** muestra PDFs generados para el caso y en conversaciones vinculadas. Cada archivo indica la relación, fecha, idioma y alcance. **Abrir PDF en otra pestaña** usa el visor del navegador; también puede descargarse.
6. **Actividad** muestra actor, fecha y explicación de los eventos. Actualizar incluye las lecturas y descargas recién realizadas. El JSON permanece sólo en administración.
7. **Contexto para la revisión** resume el historial comparable y las condiciones de servicio disponibles del mismo titular. Señala información que falta contrastar; los problemas no financieros no exigen movimiento o contrato. Las condiciones y publicaciones aportan contexto, no autorización.
8. **Decidir el siguiente paso**, dentro del resumen, permite iniciar la revisión y aprobar o rechazar una devolución que el cliente ya solicitó. Ambas decisiones requieren motivo, confirmación y contraseña del administrador. Aprobar abona el importe completo mostrado a la cuenta del titular. Rechazar no genera un abono y no cancela el pago original. No permite abonos parciales, revertir un abono aprobado ni cancelar pagos pendientes.
9. Después de decidir y comprobar que no hay gestiones pendientes, **Resultado y opinión** registra el resumen de resolución y programa el cierre de atención existente. Una decisión de devolución no cierra el reclamo por sí sola. Un pago pendiente sigue impidiendo el cierre.
10. El cliente abre **Mis reclamos → Actualizar casos** sin volver a iniciar sesión: verá decisión, motivo, administrador, fecha, importe y referencia de abono. **Ver abono en Movimientos** actualiza los datos y filtra el movimiento exacto, sin recargar la aplicación ni perder el borrador o la llamada del chat. El botón **Actualizar** del expediente también vuelve a consultar la resolución.

Para mostrar un PDF durante el pitch, el mismo titular puede pedir en otra conversación un resumen PDF de ese reclamo, seleccionarlo y generarlo. El archivo se enlaza por su referencia guardada, no por coincidencias en el texto. Un PDF general de la cuenta no se atribuye automáticamente a un reclamo.

## Alcance implementado

- Lista paginada de 20 documentos; consultas de metadatos no leen el contenido binario.
- Rutas administrativas bajo `/api/admin/users/{userId}/requests/{requestId}/documents` y `/{documentId}`. La segunda abre el PDF; `?download=true` lo descarga.
- Servidor verifica rol, titular del caso y relación del documento. Una lectura no amplía la relación hacia otros archivos. Cliente sin rol: 403; referencia ajena o no vinculada: 404.
- Auditoría de lista, apertura y descarga con actor, titular y caso; no guarda el contenido del PDF. Respuestas sin caché.
- Sólo PDFs generados por la aplicación. No se implementó carga de archivos arbitrarios, análisis antivirus, OCR ni documentos externos.
- El administrador no tiene asignación de cola, SLA, mensajería al cliente ni cierre definitivo nuevos. Se conservan revisión, derivación y decisión de devolución existentes.

## Verificación repetible

```powershell
.venv-app/Scripts/python.exe -m pytest backend/tests/test_admin_documents.py backend/tests/test_claim_trace.py -q
npm run test:claims
npm run build
node scripts/nexqori-admin-decision.mjs
```

La prueba visual requiere Compose. Crea usuarios de verificación distintos de los manuales y comprueba tres reclamos, conversaciones, PDF, auditoría y accesibilidad ES/EN/PT. Guarda accesos y evidencias privadas bajo `.local/verification/claims/`. No llama a modelos externos ni reinicia clientes anteriores.

El ensayo `nexqori-admin-decision.mjs` usa un banco aislado en el puerto 5192, sin Compose ni proveedores. Verifica aprobación, rechazo y pago pendiente en ES/EN/PT; comprueba el resultado desde una sesión de cliente ya abierta, el abono único, conservación del pago original, móvil y accesibilidad. También prueba encuesta sin guardar → Actualizar → valores conservados, y retiene la respuesta de un guardado mientras actualiza para comprobar que la escritura no se cancela ni deja los controles bloqueados. Guarda el informe en `.local/verification/admin-decision-*`. Debe ejecutarse con 5192 libre. Pruebas de API: `python -m pytest backend/tests/test_admin_case_decision.py backend/tests/test_claim_trace.py backend/tests/test_operations.py -q`.
