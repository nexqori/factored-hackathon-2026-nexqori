# Chat del banco, pagos y reclamos

Actualizado el 2 de octubre de 2026, America/Lima.

La app bancaria en `http://localhost:5180` usa el mismo intérprete de atención que el editor. El pago de teléfono se registra en el libro local y aparece en **Movimientos**, con comprobante. **Mis reclamos** muestra la evolución de los problemas. **Mis solicitudes** conserva otros trámites, como consultas de crédito.

## Probar desde el banco

1. Ejecuta `npm run setup` sólo si todavía no tienes configuración local. Luego ejecuta `docker compose up --build -d`.
2. Abre el banco e inicia sesión. Las credenciales iniciales están en tu `.env` local; no las publiques. Andrea tiene correo `andrea@nexqori.com` y un recibo de octubre por **299,00 MXN**.
3. Abre **Servicios**, busca teléfono y entra al servicio. El recibo contiene línea, periodo, vencimiento e importe; el cliente elige la cuenta.
4. Pulsa **Revisar pago**, marca la confirmación y pulsa **Confirmar pago**. La pantalla muestra **Pago realizado**, ID `PAY-…` y movimiento `TX-…`.
5. En **Movimientos**, abre el pago para recuperar el comprobante. Recargar o reintentar no crea otro débito. El pago no crea un folio en solicitudes ni en reclamos.

El recibo de Andrea es un fixture persistente y ficticio de octubre de 2026. No procede de un recaudador ni del historial personal del dataset. No se crean cargos al registrarse ni se renueva automáticamente la factura cada mes. Una cuenta sin recibos muestra un estado vacío. Los proveedores del catálogo no prueban un convenio de recaudación.

## Conversación con Jev y Luna

Las claves configuradas en `.local/intent-lab/providers.env` se cargan en la API, nunca en React. Compose admite que el archivo no exista; en ese caso el chat indica que falta conectar un proveedor. Tras cambiar claves de ese archivo, recrea la API con `docker compose up -d --force-recreate api`. No uses `docker compose config` para compartir diagnósticos: puede mostrar secretos resueltos.

1. En el asistente, inicia una conversación nueva. Abre **Registros para esta conversación** y selecciona un movimiento del titular. También puedes empezar desde **Preguntar al asistente** en el detalle de un movimiento.
2. Escribe el problema. Jev deriva consulta/problema y elige el contrato. El motor consulta las herramientas permitidas y Luna extrae lo que declaró el cliente.
3. Responde las preguntas pendientes. No se vuelve a clasificar mientras se reúnen los datos. Para un importe incorrecto, «me cobraron de más» no completa la comparación: se pide el importe esperado en cifras.
4. Revisa **Seguimiento de la conversación**: caso, registros consultados, pasos, tiempos y JSON. El historial recupera el resultado sin ejecutarlo otra vez.
5. Cuando exista una propuesta, pulsa **Revisar y registrar reclamo**, revisa el relato y confirma. El servidor crea o recupera el folio del movimiento. No crea el reclamo al clasificar ni al consultar evidencia.
6. Abre **Mis reclamos** para ver estado, conversación, lecturas, responsables y decisiones. **Revisar reclamo** abre las acciones existentes: pedir revisión de devolución o atención. La devolución exige aprobación del administrador; proteger una tarjeta sigue exigiendo contraseña y confirmación en Tarjetas.

Una conversación registrada conserva su expediente. Los mensajes posteriores quedan vinculados al mismo reclamo. Para un problema distinto se usa **Nueva**. La voz mantiene sólo su entrada visual y continúa aplazada.

## Motor y persistencia

- `BANK_ASSISTANT_FLOW=true` habilita el adaptador; `/api/assistant` conserva la ruta guiada para clientes anteriores. La UI usa `/api/assistant/flow` cuando está conectado.
- La API lee el maestro guardado en el directorio local del editor montado como sólo lectura. Si no existe, utiliza la plantilla compartida. Valida el grafo y rechaza los bloques de diagnóstico/avisos locales en una sesión bancaria. Cada ejecución conserva su copia de reglas; las ediciones afectan conversaciones nuevas.
- `conversation_flows` conserva clasificación, contrato, datos declarados, evidencia y traza por conversación. `assistant_turns` conserva la respuesta de cada clave de idempotencia. Las conversaciones y los mensajes siguen en sus tablas originales.
- Un turno bancario se confirma de forma atómica junto con sus lecturas auditadas y mensajes. No exporta checkpoints a los JSON del LAB. Ante caída del proceso antes del commit, el turno no queda confirmado: un reintento explícito puede consumir otra llamada de modelo, pero no ejecutar un pago. El chat no ofrece ejecución por bloques; esa inspección corresponde al editor.
- Las herramientas reciben identidad de la sesión, no del texto ni del modelo. Se comprueba el titular de movimiento, cuenta, folio y conversación. Los registros bancarios y las credenciales no se agregan a los mensajes enviados a proveedores. El texto escrito o pegado por el cliente sí se usa para clasificar y extraer contexto.
- El panel administrativo puede leer la conversación y su evaluación a través de la consulta auditada existente. Los resultados guardados describen lo observado en ese turno; los datos actuales del expediente pueden haber cambiado después.

## Pago local y API

`phone_bills` guarda recibos del titular. `bill_payments` guarda un comprobante inmutable y referencias con claves foráneas compuestas por titular.

| Ruta | Resultado |
| --- | --- |
| `GET /api/phone-bills` | Recibos propios e ID del pago, si existe. |
| `POST /api/phone-bills/{id}/pay` | Exige cuenta propia, confirmación y clave de idempotencia. El importe procede del recibo. |
| `GET /api/payments/{id}` | Comprobante del titular; 404 para otra persona. |
| `POST /api/services/phone-bill/requests` | Devuelve `use_bill_payment`; ya no registra solicitudes telefónicas. |
| `POST /api/assistant/flow` | Ejecuta o continúa un turno del flujo, sin escrituras financieras. |
| `GET /api/conversations/{id}/flow` | Recupera el resultado propio sin ejecutar. |
| `POST /api/conversations/{id}/claim` | Registra el reclamo tras confirmación y con contrato derivado por el servidor. |

El pago bloquea titular, recibo y cuenta; comprueba saldo y moneda; inserta un movimiento negativo, resta el saldo y registra auditoría en un commit. Una restricción única impide pagar dos veces el mismo recibo. Los errores no crean un débito parcial. El comprobante no equivale a liquidación con una compañía telefónica externa: esta implementación tiene libro bancario local, sin procesador de pagos conectado. Los otros formularios del catálogo conservan su alcance documentado de solicitudes.

La migración `e2715ba946c0` agrega tablas sin modificar saldos, mensajes ni casos anteriores. Los formularios antiguos de teléfono se conservan como solicitudes históricas; no se convierten en pagos ni se descuentan retroactivamente.

## Pruebas repetibles

```powershell
npm test
npm run build
.venv-app/Scripts/python.exe -m pytest backend/tests -q
npm run test:payments
npm run test:chat:flow
npm run test:claims
```

- `test:payments` requiere Docker :5180. Crea tres titulares ficticios de verificación en PostgreSQL. Prueba ES/EN/PT, importe precargado, confirmación, pérdida de respuesta después del commit, primer pago concurrente, reintento, lectura tras recarga y comprobante en Movimientos. No modifica los saldos de Andrea. Guarda resultados y accesos privados en `.local/verification/payments/`; `latest.json` señala el paquete reciente.
- `test:chat:flow` requiere el entorno `.venv-app` y el puerto 5192 libre. Usa API e intérprete reales, SQLite aislado y proveedores controlados. Prueba tres contratos en ES/EN/PT, nueve conversaciones, preguntas/continuación, selección de registros, alta y trazabilidad del reclamo. Verifica que recuperar el historial no repita modelos. No usa claves ni compara calidad de proveedores.
- Los scripts antiguos de navegación/experiencia/catálogo/acciones comprueban la ruta guiada mediante una respuesta controlada de capacidades en el navegador. La prueba del chat conectado está separada.
- Para un recorrido manual nuevo, entra con Andrea y usa sus movimientos. Para pruebas reproducibles sin alterar sus datos, utiliza los accesos del paquete privado de verificación. No publiques esos archivos ni capturas con credenciales.

El editor conserva sus pruebas `test:lab:steps`, `test:lab:master` y `test:lab:bank`. Jev/Luna pueden fallar o pedir más información; en ese caso la app muestra la evaluación incompleta y no declara una operación realizada.
