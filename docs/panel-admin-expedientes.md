# Expediente administrativo

Acceso local: http://localhost:5180/admin/complaints con una cuenta de administración.

1. El cliente registra y confirma un reclamo desde su chat. El reclamo conserva su identificador y movimiento, si existe.
2. En administración, pulsa **Actualizar casos**, filtra por cliente y selecciona el reclamo.
3. **Resumen** muestra el relato registrado, importe, referencia, estado y siguiente paso. Una devolución pendiente requiere una decisión distinta de la revisión del reclamo.
4. **Conversaciones** permite leer mensajes originales y consultar la evaluación del asistente de forma desplegable. Una conversación sobre el mismo movimiento aporta contexto; no demuestra por sí sola que todos sus mensajes correspondan al reclamo.
5. **Documentos** muestra PDFs generados para el caso y en conversaciones vinculadas. Cada archivo indica la relación, fecha, idioma y alcance. **Abrir PDF en otra pestaña** usa el visor del navegador; también puede descargarse.
6. **Actividad** muestra actor, fecha y explicación de los eventos. Actualizar incluye las lecturas y descargas recién realizadas. El JSON permanece sólo en administración.
7. **Gestionar caso** abre las acciones existentes: iniciar revisión y decidir una devolución solicitada. La aprobación exige confirmación y contraseña del administrador. Leer el expediente no modifica saldo ni estado.

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
```

La prueba visual requiere Compose. Crea usuarios de verificación distintos de los manuales y comprueba tres reclamos, conversaciones, PDF, auditoría y accesibilidad ES/EN/PT. Guarda accesos y evidencias privadas bajo `.local/verification/claims/`. No llama a modelos externos ni reinicia clientes anteriores.
