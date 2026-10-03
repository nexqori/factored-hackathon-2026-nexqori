# Consultas y PDF en el banco

Las consultas usan la conversación persistente del banco y lecturas limitadas al titular autenticado. Jev distingue consulta de problema y selecciona la intención. La consulta de movimientos responde con los cinco más recientes y permite abrir su detalle. Las tarjetas se muestran enmascaradas. El saldo conserva su lectura auditada.

## Documentos

1. Inicia una conversación y escribe «Quiero descargar mi estado de cuenta en PDF». También puedes preparar el PDF después de consultar saldo, movimientos, tarjetas o seguimiento.
2. Pulsa **Preparar PDF**. Elige estado de cuenta informativo, resumen de productos o seguimiento de solicitudes.
3. Selecciona todos tus registros o una cuenta/solicitud concreta. Para movimientos, elige ambas fechas o todo el historial disponible.
4. Pulsa **Generar PDF**. Se abre **Mis solicitudes → Documentos solicitados**, con el documento destacado, descarga y detalle de alcance, período y registros incluidos. También permanece en el chat y su historial.

Las fechas incluyen ambos días en `America/Mexico_City`, como los movimientos del banco. El intervalo personalizado admite hasta 366 días entre fechas. Hay un límite de 250 filas por sección, 20 documentos por conversación y 2 MB por archivo. Si se excede el número de filas, se pide reducir la selección; no se entrega un documento truncado.

El saldo del PDF es el saldo actual al generar el archivo, no un saldo de apertura o cierre del periodo. Los documentos son informativos: no son certificados firmados ni comprobantes fiscales. No se envían por correo automáticamente. El PDF conserva la instantánea original aunque después cambien los saldos o las solicitudes.

## Integración de Santiago

Origen: `codex/bank-intent-es-pt`, commit `3d85c57ead66031ffda860cdab7b83cc05987669`, autor Santiago Leyva. Se revisaron los seis commits de esa rama y se adaptaron el generador ReportLab, las tres plantillas y sus traducciones. [Manifiesto y hashes originales](../backend/document_templates/provenance.json).

Se incorporaron a la conversación PostgreSQL existente. El adaptador original de la rama guardaba conversaciones y archivos en memoria por sesión; sustituir el chat actual por ese adaptador habría perdido historial, trazabilidad y recorridos de reclamos. La recuperación original podía enviar hechos bancarios al LLM. Aquí los registros, la composición de respuestas y el PDF permanecen en el servidor; el proveedor sólo recibe contexto conversacional permitido.

La selección de tipo, alcance y periodo usa un formulario explícito. Un texto del modelo no puede elegir un titular, introducir SQL/HTML/rutas, ejecutar pagos ni aprobar documentos de otra persona. Los notebooks de experimentación y los adaptadores alternativos no se activan en el banco.

## API y persistencia

- `POST /api/conversations/{id}/documents`: sesión de cliente, CSRF, conversación propia con consulta válida, referencias propias y clave de idempotencia. Guarda mensaje, PDF y auditoría juntos.
- `GET /api/documents/{id}`: vuelve a validar sesión y titular, audita descarga y responde `application/pdf`, `attachment`, `Cache-Control: no-store`.
- `GET /api/documents`: lista propia paginada de 20 documentos, sin cargar sus binarios. El parámetro `selected` conserva el acceso directo al documento propio aunque pase a otra página. No crea una solicitud de crédito ni un reclamo.
- `chat_documents`: propietario, conversación, mensaje, tipo, idioma, nombre seguro, clave/fingerprint, archivo y fecha. El historial sólo carga metadatos; el binario se recupera al descargar.
- `documents` amplía la taxonomía viva de consultas. El corpus NLP congelado conserva sus casos originales; esta ampliación no se presenta como una mejora medida del benchmark.

## Pruebas repetibles

```powershell
.venv-app/Scripts/python.exe -m pytest backend/tests/test_query_documents.py -q
.venv-app/Scripts/python.exe scripts/verify-query-pdfs.py
npm run test:banking
```

El segundo comando genera tres ejemplos ficticios en `.local/verification/query-pdfs/`. Las pruebas verifican tres idiomas, historial, reintentos, datos ajenos, permisos, periodos, límites y ausencia de escrituras financieras. Las capturas PDF se revisan con Poppler; la extracción de texto por sí sola no verifica el diseño.
