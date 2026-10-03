# Pagos de servicios y transferencias

La app consulta un recibo por proveedor y referencia antes de cobrarlo. El importe total procede del servidor. El cliente sólo puede elegir un abono parcial cuando ese recibo lo permite. Las transferencias confirman un destinatario de Nexqori y registran el débito y el crédito en la misma transacción de base de datos.

Los resultados se consultan en **Movimientos** con su comprobante. Pagar o transferir no crea un reclamo ni una solicitud. **Mis solicitudes** conserva los trámites; **Mis reclamos** conserva los problemas y su seguimiento.

Esta implementación usa el libro local de Nexqori. No conecta compañías recaudadoras, SPEI u otra red bancaria. Los nombres de proveedores proceden del catálogo documentado, pero los recibos de prueba son ficticios y no prueban convenios con esas empresas.

## Pagar un servicio

1. Entra a **Servicios** y selecciona teléfono, internet, televisión o servicios públicos.
2. Introduce el número de teléfono o código de cliente. También puedes elegir una referencia guardada del mismo titular.
3. Consulta los recibos. Si hay varios periodos para esa referencia, elige uno. Comprueba empresa, referencia, periodo, vencimiento, importe original, importe pagado y saldo pendiente.
4. Elige una cuenta de origen. El total pendiente no es editable. Si el recibo admite abonos, puedes seleccionar pago parcial e indicar un importe positivo que no supere el pendiente.
5. Revisa los datos, marca la confirmación y confirma el pago.
6. Conserva el comprobante `PAY-…`. Un abono muestra el saldo restante. Un pago inmediato completo deja el recibo liquidado; un pago pendiente conserva ese estado hasta que se resuelva su procesamiento. Puedes iniciar otro pago y consultar otra referencia.

Cambiar de referencia borra la selección del recibo anterior. Si otro pago cambió el pendiente desde la consulta, el servidor rechaza el importe desactualizado; vuelve a consultar antes de confirmar. Reintentar la misma petición devuelve el comprobante original sin otro débito.

Los recibos de Andrea permiten este recorrido local:

| Servicio | Referencia | Importe original | Permite abono |
| --- | --- | ---: | --- |
| Empresa Telefónica | `5500000001` | 299,00 MXN | No |
| Empresa Telefónica | `5500000002` | 199,00 MXN | Sí |
| Internet Plus | `INT-4821001` | 459,00 MXN | Sí |
| Cable TV | `TV-4821001` | 249,00 MXN | No |
| Servicios Públicos | `LUZ-4821001` | 520,00 MXN | Sí |

Son recibos persistentes de octubre de 2026. Si ya pagaste uno, se conserva su estado: reiniciar la app no repone la deuda ni cobra otra mensualidad. La prueba automatizada crea nuevos titulares para evitar modificar estos registros existentes.

### Teléfono pendiente de procesamiento

El recibo telefónico local permite elegir **Inmediato** o **Pendiente de procesamiento** antes de revisar y confirmar. Inmediato sigue siendo el comportamiento por defecto. Los demás servicios no admiten la opción pendiente.

La opción pendiente permite probar una consulta o un reclamo sobre un pago que ya se descontó de la cuenta y todavía no está completado. Registra un único débito, un movimiento con estado `pending` y un comprobante con el mismo estado. La pantalla debe indicar **Pendiente de procesamiento**; no debe afirmar **Pago realizado** ni que la compañía recibió el dinero. El importe ya debitado se muestra por separado del importe completado.

El pendiente se excluye del importe disponible para pagar de nuevo. Si el recibo admite abonos, puede quedar una parte completada, otra en procesamiento y un resto aún por pagar. La suma de lo completado y lo pendiente nunca puede superar el importe original. Reintentar la misma petición recupera su comprobante; una nueva petición contra un recibo cubierto por pagos pendientes recibe `bill_in_processing`.

Desde **Movimientos → Preguntar al asistente**, el cliente puede consultar el estado o iniciar un reclamo sobre ese movimiento. La lectura utiliza el registro del mismo titular y no representa logs de un recaudador externo. Consultar, recargar, reiniciar la aplicación o registrar un reclamo no completa ni vuelve a debitar el pago.

Este escenario no programa una fecha futura y no tiene temporizador, trabajador de liquidación ni conexión con la compañía telefónica. El pendiente permanece hasta una intervención explícita fuera de este recorrido. Una futura resolución necesita un contrato propio: autorización de servidor, evento auditado e idempotente, comprobante original conservado y estado actual separado. Confirmar su procesamiento no debe hacer otro débito; cancelar requiere un crédito compensatorio único y enlazado. No existe todavía un endpoint que haga esa resolución.

## Transferir a otra persona

1. Abre el servicio de transferencia e introduce la referencia completa de la cuenta del destinatario.
2. Consulta al destinatario. Comprueba su nombre y la terminación de la cuenta que devuelve el servidor.
3. Selecciona tu cuenta de origen, el importe y una nota opcional.
4. Revisa los datos y confirma. La comprobación del destinatario dura diez minutos; si vence, vuelve a consultarlo.
5. Revisa el comprobante `TRF-…` en **Movimientos**. El destinatario ve su movimiento de entrada con una referencia de transacción propia.

No se permite enviar a una cuenta del mismo titular mediante este recorrido. El destinatario debe tener una cuenta o ahorro en MXN dentro de este libro local. Su saldo no se muestra al buscarlo. La referencia de Andrea termina en `4821`; la de Mateo es `700000000000001103`. Usa los titulares nuevos del paquete de verificación para pruebas repetibles.

## Contratos de API

Todas las rutas requieren una sesión vigente del cliente. Las solicitudes POST requieren origen permitido y token CSRF.

| Ruta | Condiciones y resultado |
| --- | --- |
| `GET /api/service-bills/references` | Lista las referencias guardadas del titular; no lista cuentas de otras personas. |
| `POST /api/service-bills/lookup` | Recibe `serviceId` y `reference`; devuelve sólo recibos del titular de esa combinación. Registra la consulta en auditoría. |
| `POST /api/service-bills/{id}/pay` | Recibe `accountId`, `confirmed: true`, `requestKey`, `mode` y `expectedOutstandingMinor`. Sólo `mode: partial` acepta `amountMinor`. `processingMode` es `immediate` por defecto; sólo un recibo telefónico local admite `pending`. |
| `GET /api/payments/{id}` | Recupera un comprobante propio. Un tercero recibe 404. |
| `POST /api/transfers/recipient` | Consulta una referencia exacta de 12 a 18 dígitos y devuelve `quoteId`, nombre, moneda, referencia, terminación y vencimiento. |
| `POST /api/transfers` | Recibe `quoteId`, `accountId`, `amountMinor`, `note` opcional, `confirmed: true` y `requestKey`. Confirma la transferencia una sola vez. |
| `GET /api/transfers/{id}` | Sólo emisor y destinatario pueden leerlo; cada uno recibe su dirección y referencia de movimiento. |

El importe se expresa en unidades menores enteras: `12500` equivale a 125,00 MXN. La captura de abonos y transferencias acepta hasta `100000000` unidades menores; es un límite técnico local, no una política acreditada de un banco externo.

La consulta de un recibo devuelve `paidMinor` (completado), `pendingMinor` (debitado y aún en procesamiento), `outstandingMinor` (disponible para pagar), `paymentStatus`, `pendingPaymentId` y las `processingOptions` permitidas por el servidor. El cliente no puede elegir un estado arbitrario ni marcar como completado un pendiente existente.

Los endpoints antiguos `/api/phone-bills` y `/api/phone-bills/{id}/pay` se conservan para compatibilidad telefónica y no aceptan un modo de procesamiento nuevo. No permiten pagar recibos de otros servicios. Si un recibo ya está cubierto por un pago pendiente, la ruta antigua puede recuperar ese comprobante sin otro débito. Crear solicitudes nuevas de facturación o transferencias por `/api/services/{id}/requests` devuelve `use_bill_payment` o `use_transfer`, respectivamente.

## Persistencia y seguridad

- `phone_bills` conserva su nombre histórico e incorpora `service_id` y `allow_partial`. La combinación titular, servicio, referencia y periodo identifica un recibo. `bill_payments` admite varios abonos y conserva sus comprobantes inmutables.
- El servidor bloquea titular, recibo y cuenta, recalcula el pendiente y valida saldo. Registra débito, comprobante y auditoría en un solo commit. No usa un importe total enviado por el navegador.
- `transfer_quotes` vincula la comprobación del destinatario al emisor y a un vencimiento. `bank_transfers` enlaza ambos titulares, ambas cuentas y ambos movimientos. Los bloqueos se toman en orden estable para evitar interbloqueos entre transferencias opuestas.
- Cada pago o transferencia conserva una clave de idempotencia por titular y una huella de sus parámetros. El mismo envío recupera el resultado. Cambiar los parámetros con la misma clave produce conflicto. Un reintento de una transferencia completada sigue recuperando su comprobante aunque haya vencido la consulta del destinatario.
- El modo inmediato conserva la huella de los pagos creados antes de añadir `processingMode`. Cambiar la misma clave de inmediato a pendiente produce conflicto. Los pendientes registran `phone_bill_pending`, no un evento que afirme que el pago se completó.
- Las claves foráneas compuestas y la autorización de servidor comprueban el dueño de cuentas, recibos y movimientos. Un administrador no usa estas rutas para operar como cliente.
- Un fallo al guardar la auditoría revierte las modificaciones financieras de ese intento. Las herramientas del chatbot no ejecutan estas operaciones ni convierten una clasificación en autorización.

La migración `f381a620d734` añade estas capacidades y los documentos del chat. Conserva pagos y solicitudes anteriores; no los transforma en nuevas operaciones. Su reversión requiere restaurar un respaldo verificado para conservar el historial financiero.

## Comprobar la implementación

Pruebas aisladas de API, sin claves ni red externa:

```powershell
.venv-app/Scripts/python.exe -m pytest backend/tests/test_service_payments.py backend/tests/test_transfers.py backend/tests/test_catalog.py backend/tests/test_phone_payments.py -q
.venv-app/Scripts/python.exe -m pytest backend/tests/test_pending_phone_payments.py -q
```

Las pruebas cubren búsquedas exactas, varios recibos y referencias, abono y saldo restante, comprobantes, reintentos, saldo insuficiente, confirmación, datos ajenos, CSRF, roles, consulta vencida, conservación del dinero y reversión ante fallo de auditoría. La base SQLite aislada valida el comportamiento; no reproduce los bloqueos de PostgreSQL. La aceptación de interfaz y concurrencia se realiza por separado contra Docker local.

La suite de teléfono pendiente añade separación de importes completados/en procesamiento, abonos combinados, compatibilidad de huellas antiguas, reintento tras error de guardado y lectura/registro de reclamo en ES/EN/PT. No consume modelos ni modifica la cuenta local de Andrea: usa una base aislada por prueba.

Con Docker iniciado, `npm run test:payments:pending` valida el recorrido en navegador con tres titulares nuevos: confirmación, comprobante en proceso, débito único aun al perder la respuesta, recuperación tras recargar y consulta de evidencia desde Movimientos. Conserva informes, capturas y accesos privados en `.local/verification/deferred-payments/`. Usa respuestas controladas para evitar llamadas a modelos; las lecturas de movimientos proceden de PostgreSQL.

El helper [banking-cases-fixtures.py](../scripts/banking-cases-fixtures.py) admite `integratedBanking: true` al preparar el paquete para la interfaz. Sólo funciona con `NEXQORI_LOCAL_VERIFY=1` y la base local de Compose. Crea cinco recibos por titular, referencias de transferencia, una conversación de documentos con clasificación controlada y un beneficiario nuevo. No llama a Jev ni a LLM. Las credenciales generadas se guardan únicamente en `.local`, nunca en documentación pública.

`mode: verify_banking` verifica directamente en PostgreSQL los seis pagos (internet lleva dos abonos), la transferencia, los tres documentos y las auditorías de cada titular. Comprueba los créditos del beneficiario y una huella de los registros financieros y casos de otros titulares. Este modo corresponde al recorrido de aceptación completo, no a un paquete donde sólo se ejecutó una parte.

Documentos y flujo conversacional: [chat del banco](chat-bancario-y-pagos.md). Fuentes y límites del catálogo: [catálogo de servicios](catalogo-servicios.md).
