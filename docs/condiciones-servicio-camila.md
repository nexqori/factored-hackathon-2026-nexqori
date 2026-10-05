# Condiciones del servicio en el reclamo de Camila

Este caso es construido para las pruebas. No procede de un contrato real del dataset.

El plan **Teléfono Esencial** tiene base mensual fija de **299 MXN**, impuestos incluidos, durante doce meses desde el primer recibo del escenario. Los cargos adicionales requieren aceptación del cliente. El recibo más reciente es de **459 MXN**: hay **160 MXN sobre la base** que necesitan explicación. El pago continúa pendiente; comparar condiciones no lo liquida.

## Recorrido

1. Entrar con Camila y abrir Movimientos. Buscar Empresa Telefónica y filtrar Pendiente.
2. Abrir el detalle: muestra historial, condiciones del servicio y aviso de tarifa por separado.
3. Preguntar al asistente por ese movimiento: «Me cobraron de más en el teléfono. Revisa el importe».
4. Revisar las aclaraciones y el resumen. El contrato es evidencia adicional del mismo flujo; no se vuelve a clasificar ni se crea otro reclamo automáticamente.
5. Confirmar el registro. Administración ve la comparación en el relato y la conversación del expediente. Debe verificar conceptos adicionales y cambios aceptados antes de decidir. El formulario de atención y su cierre siguen su propio proceso.

El aviso público de 459 MXN no actualiza automáticamente las condiciones del cliente. Sin un contrato único para todo el período, se pide revisión; no se inventa un importe esperado. Tampoco se marca como correcto un cargo sólo por quedar dentro de la base.

## Persistencia y límites

- `service_agreements` guarda titular, referencia del servicio, proveedor, plan, versión, moneda, vigencia e importe. La migración `eab672514c90` sólo añade esa tabla.
- El lector exige el recibo ligado al movimiento del mismo titular, coincidencia exacta de línea/plan/proveedor/moneda y cobertura de todo el mes. Períodos inválidos, cambios a mitad de mes y contratos solapados pasan a revisión.
- La preparación de escenarios añade las condiciones sin reescribir recibos, saldo, conversaciones ni reclamaciones existentes. Repetirla no duplica; condiciones previas distintas provocan un error, no se sobrescriben.
- El contexto queda dentro del servidor bancario y su lectura auditada. No se envía el contrato ni los registros a Jev/LLM/GPT-Live. El resumen puede editarse antes de confirmar; la evidencia leída permanece en el flujo.
- No hay carga de PDFs, OCR, búsqueda legal, edición libre de cláusulas ni aprobación automática de devoluciones en este alcance. Las condiciones son registros estructurados de ejemplo, sin atribuir aceptación real a Camila.

## Preparación y comprobación

Después de actualizar y migrar la API, `npm run test:spending:prepare` añade también las condiciones del paquete local `equipo-ux`. Requiere el manifiesto privado que ya usa ese equipo; no se publican credenciales.

```powershell
.venv-app/Scripts/python.exe -m pytest backend/tests/test_service_agreements.py backend/tests/test_spending.py backend/tests/test_migrations.py -q
npm run build
npm run test:spending
```

Las pruebas usan usuarios aislados y proveedores controlados. Verifican tres idiomas, contexto del reclamo, publicación de tarifa, aislamiento, idempotencia y ausencia de débitos o abonos automáticos.
