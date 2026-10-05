# Chat del banco, pagos y reclamos

Actualizado el 3 de octubre de 2026, America/Lima.

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

1. En el asistente, inicia una conversación nueva. La bienvenida muestra sugerencias, sin el botón **Elegir movimiento**. Puedes escribir el problema directamente, seleccionar un movimiento en **Detalles** o empezar desde **Preguntar al asistente** en un movimiento. El selector aparece en la conversación después de empezar o de seleccionar explícitamente un registro.
2. Al enviar, tu mensaje aparece de inmediato y el campo se vacía. **Pensando…** permanece visible hasta recibir la respuesta. Jev deriva consulta/problema y elige el contrato. Si falla la respuesta, se restaura el texto y el contenido pegado. Reintentar la misma petición conserva su clave para recuperar el turno ya guardado sin duplicarlo.
3. Responde las preguntas pendientes. No se vuelve a clasificar mientras se reúnen los datos. Para un importe incorrecto, «me cobraron de más» no completa la comparación: se pide el importe esperado en cifras.
4. El chat muestra los mensajes. **Detalles** reúne la selección de registros y el seguimiento en una sola vista. Activa **Un movimiento**, **Un caso**, ambos o ninguno. **Usar selección** aplica los registros juntos; **Continuar sin selección** retira los anteriores. **Volver al chat** o cerrar descarta los cambios del formulario. Abrir o cerrar conserva el borrador y no ejecuta modelos. El cliente no ve JSON, códigos de auditoría, pasos del motor ni tiempos técnicos; administración y el editor conservan esas herramientas. **Conversaciones** recupera el historial y los registros elegidos sin ejecutarlos otra vez.
5. Cuando exista una propuesta, el chat muestra **Esto es lo que encontré**: problema declarado, movimiento propio (importe, fecha, referencia y estado) y aclaraciones útiles. Pide revisar esos datos antes de registrar el reclamo, sin afirmar que ya se asignó un supervisor o se realizó una devolución. Pulsa **Revisar y registrar reclamo**; puedes corregir el resumen antes de confirmar. El registro guarda un mensaje con el número de caso, el resumen y el siguiente paso; recargar o reintentar no lo duplica.
6. Abre **Mis reclamos** para ver estado, conversación, lecturas, responsables y decisiones. **Revisar reclamo** abre las acciones existentes: pedir revisión de devolución o atención. La devolución exige aprobación del administrador; proteger una tarjeta sigue exigiendo contraseña y confirmación en Tarjetas.

Una conversación registrada conserva su expediente. Los mensajes posteriores quedan vinculados al mismo reclamo. Para un problema distinto se usa **Nueva**. La voz mantiene sólo su entrada visual y continúa aplazada.

### Cobro sugerido y confirmación

Para un cargo no reconocido, importe incorrecto o pago pendiente sin movimiento seleccionado, el banco consulta de forma auditada los últimos 20 movimientos del titular. Propone el débito más reciente relacionado por proveedor, servicio, fecha o referencia. Si el relato es genérico, propone el débito más reciente; si se menciona un servicio conocido sin coincidencias, pide elegir el registro. La búsqueda es determinista y acotada: no es una búsqueda semántica de todo el historial.

La propuesta muestra empresa, estado, importe, fecha y referencia. **Sí, es este** selecciona el movimiento y continúa reuniendo contexto. También admite una respuesta breve equivalente en ES/EN/PT. **Elegir otro** abre los registros propios; puedes seleccionar allí y enviar tu aclaración. Un «No, es otro» descarta la propuesta anterior. Una fecha completa (`dd/mm/aaaa`, o `mm/dd/yyyy` en inglés) o una referencia permite buscar otra coincidencia; se mantiene la confirmación antes de vincularla. Las fechas usan America/Mexico_City, igual que Movimientos.

Proponer no convierte el movimiento en evidencia del caso, ni registra un reclamo o una devolución. La referencia sólo queda vinculada al confirmarla o seleccionarla explícitamente. **Elegir movimiento** y **Cambiar movimiento** muestran concepto, fecha, importe y referencia. Antes de registrar el reclamo, aplicar un cambio descarta la evidencia del movimiento anterior y vuelve a Contexto con el mismo contrato y relato. Después del registro, otro movimiento requiere una conversación nueva. Las consultas y cambios explícitos se auditan; sus datos no se añaden al historial que reciben Jev/Luna.

La vista previa del resumen incluye un token de versión. Si cambia la conversación o el movimiento, se exige preparar otra vista antes de confirmar. Registrar guarda reclamo, mensaje y auditoría en una sola transacción. El resumen editado no se envía al modelo como parte del historial.

Después de confirmar un movimiento, el chat retira **Elegir movimiento** y **Cambiar movimiento**. Presenta los hallazgos y el siguiente paso de revisión. Una corrección explícita sigue disponible en **Detalles** antes del registro; el movimiento no cambia por presentar el resumen. Los hallazgos bancarios se guardan para el cliente, pero el historial de Jev/Luna conserva sólo el mensaje general sin datos bancarios.

El formulario no exige combinar un caso con un movimiento. Si se eligen ambos, deben corresponder al mismo expediente para que sus evidencias se puedan combinar. El servidor mantiene la comprobación de titularidad y de referencias relacionadas. `updateSelection: true` reemplaza ambas referencias de forma explícita, incluidos valores vacíos para retirarlas. Antes del primer mensaje la selección queda preparada; en una conversación existente, aplicarla crea un turno auditado y vuelve a reunir contexto. El registro definitivo del reclamo fija sus referencias; para cambiarlas después se inicia otra conversación.

Si el cliente dice «tengo un problema con una transferencia», Jev puede reconocer la familia problema y necesitar el síntoma para elegir un contrato. La pregunta estándar debe pedir qué pasó con la transferencia, sin volver a preguntar si es consulta o problema. La siguiente respuesta conserva el relato previo. Las preguntas personalizadas por el operador siguen intactas; el texto de aclaración nunca selecciona un contrato ni autoriza una operación.

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

El resumen del movimiento incluye una [comparación histórica de pagos](comparacion-historica-pagos.md) cuando hay antecedentes comparables. Es una ayuda para revisar diferencias, no una confirmación automática de error.

```powershell
npm test
npm run build
.venv-app/Scripts/python.exe -m pytest backend/tests -q
npm run test:payments
npm run test:chat:flow
npm run test:claims
```

- `test:payments` requiere Docker :5180. Crea tres titulares ficticios de verificación en PostgreSQL. Prueba ES/EN/PT, importe precargado, confirmación, pérdida de respuesta después del commit, primer pago concurrente, reintento, lectura tras recarga y comprobante en Movimientos. No modifica los saldos de Andrea. Guarda resultados y accesos privados en `.local/verification/payments/`; `latest.json` señala el paquete reciente.
- `test:chat:flow` requiere el entorno `.venv-app` y el puerto 5192 libre. Usa API e intérprete reales, SQLite aislado y proveedores controlados. Prueba tres contratos en ES/EN/PT, nueve conversaciones, preguntas/continuación, selección de registros, alta y trazabilidad del reclamo. Verifica el mensaje visible durante la espera, propuesta y confirmación, respuesta perdida después del commit y reintento sin duplicados. Recuperar el historial no repite modelos. No usa claves ni compara calidad de proveedores.
- `npm run test:chat:live` usa las claves ya configuradas y consume llamadas de Jev/Luna. Requiere Docker :5180. Crea titulares nuevos de verificación y ejecuta [21 escenarios redactados](../tests/scenarios/conversation-basics.json): transferencia vaga y aclaración, pago pendiente, cargo desconocido, importe incorrecto, app, sucursal, atención, saldo, teléfono, transferencia nueva, negación, saludo, cambio de consulta, seguimiento y tres conversaciones de confirmación del cobro telefónico. Comprueba respuestas, clasificación, recarga, reintentos y saldos/movimientos/solicitudes intactos; no confirma pagos ni reclamos. Guarda informe y accesos privados en `.local/verification/chat-live/`. Para repetir tu ejemplo y sus variantes: `npm run test:chat:live -- --only=cobro-celular-es,phone-charge-en,cobranca-celular-pt`. Son casos de aceptación, no una medición representativa del dataset; el comando falla si un resultado no cumple lo esperado.
- Los scripts antiguos de navegación/experiencia/catálogo/acciones comprueban la ruta guiada mediante una respuesta controlada de capacidades en el navegador. La prueba del chat conectado está separada.
- Para un recorrido manual nuevo, entra con Andrea y usa sus movimientos. Para pruebas reproducibles sin alterar sus datos, utiliza los accesos del paquete privado de verificación. No publiques esos archivos ni capturas con credenciales.

El editor conserva sus pruebas `test:lab:steps`, `test:lab:master` y `test:lab:bank`. Jev/Luna pueden fallar o pedir más información; en ese caso la app muestra la evaluación incompleta y no declara una operación realizada.

## Seguimiento después de una decisión

Un nuevo mensaje en la conversación registrada vuelve a leer el expediente del titular mediante la herramienta auditada. La respuesta distingue recibido, entregado, en revisión, aprobado sin abono, devolución rechazada y reembolso realizado. Sólo anuncia el abono cuando existe un movimiento completado de devolución con el mismo titular, cuenta destino, importe y moneda. La referencia se muestra por escrito; el resumen de voz omite su lectura extensa. Estas consultas no ejecutan operaciones ni envían registros a los modelos de texto.

La consulta de un caso seleccionado en una conversación nueva utiliza el mismo resultado. El mensaje «¿Cómo va mi caso?» conserva el contexto del expediente ya registrado. Un reintento con la misma clave recupera el turno original; una pregunta nueva consulta el estado actual.

Para repetir el recorrido completo, ejecutar con el puerto 5192 libre y el frontend compilado:

    node scripts/nexqori-case-roundtrip.mjs

El ensayo registra por el chat un cargo no reconocido, revisa el mismo expediente en administración, confirma las etapas y el reembolso, vuelve al chat y abre el abono. Ejecuta ES/EN/PT con API real, base SQLite aislada y clasificadores controlados; no mide calidad del proveedor ni inicia una llamada facturada.


## Revisión simple y grabación del recorrido

Antes de registrar, «Revisar y enviar reclamo» muestra el resumen del servidor y el movimiento. «Corregir datos» permite editar; «Confirmar y enviar» es la confirmación explícita. Abrir o cerrar el resumen no registra nada. La API sigue comprobando versión, titular e idempotencia. Al confirmar se abre Mis reclamos con ese expediente, sin esperar al refresco general de la cuenta. La llamada y la conversación continúan.

Movimientos pone el listado antes del análisis. Fechas y comparación se agrupan en Más filtros; el movimiento indicado por el asistente se resalta dos segundos. Con movimiento reducido se usa un borde fijo. Mis reclamos está junto a Movimientos en el menú.

### Compra válida excepcional

En el detalle de un débito completado, «Reconozco esta compra como excepcional» pide confirmación. Guarda la declaración del titular en spending_exceptions, conserva el movimiento y lo excluye de las muestras futuras del promedio y rango habitual. No devuelve dinero, no desbloquea tarjetas ni cierra reclamos. No admite pagos pendientes, abonos o registros ajenos. La operación es idempotente por movimiento y se audita una vez.

Migración aditiva: fb7208ea46c3, tabla nueva, sin transformar el libro bancario. El análisis consulta esta marca tanto en la interfaz como en evidencia del chat. Las comparaciones ya guardadas en expedientes mantienen su evidencia histórica. El filtro Compra excepcional permite encontrar estos movimientos.

### Mensajes no admitidos

Jev distingue safe-request, prompt-injection y off-topic. Una inyección con confianza suficiente recibe una negativa de autorización; una petición claramente ajena o ininteligible recibe orientación bancaria. Confirmaciones breves, importes, referencias, errores de escritura y relatos vagos no se definen como ataques. Resultado incierto o proveedor no disponible detiene la derivación sin cambiar el caso. La clasificación es probabilística y no reemplaza permisos, confirmaciones ni validaciones del servidor.

Pruebas reproducibles: npm run build; node scripts/nexqori-voice-ui.mjs (audio y transporte simulados, sin llamadas pagadas); node scripts/nexqori-chat-flow.mjs; node scripts/nexqori-case-roundtrip.mjs; node scripts/nexqori-spending.mjs. Cada recorrido crea datos aislados.


### Confirmación por voz y vista previa (5 de octubre de 2026)

La confirmación admite una respuesta compuesta como «Sí, no reconozco ese cobro. ¿Puedes hacerme un reclamo?», incluso si conserva el final del fragmento anterior de la llamada. Sólo vincula la propuesta vigente del titular; una referencia diferente, incertidumbre, otro movimiento o texto pegado no confirman esa propuesta. No registra el caso ni autoriza una operación.

Pedir preparar el reclamo abre su vista previa cuando el flujo tiene contexto suficiente. Conserva respuestas anteriores si sólo se pide abrir el borrador, muestra la comparación disponible y permite corregir o agregar detalles. Sólo «Confirmar y enviar» registra el expediente. El detalle general permanece detrás de su botón. La voz informa el promedio comparable incluso cuando hay condiciones del plan; el estado pendiente no se describe como cargo completado ni como dinero devuelto.

Después del envío y al consultar el seguimiento, la navegación permitida abre Mis reclamos con el expediente propio seleccionado. La respuesta se basa en la decisión y el abono actuales del servidor. Ninguna URL libre del modelo puede abrir otro destino o ejecutar un reembolso.

Si la consulta comprueba un reembolso completado, abre directamente Movimientos filtrado por la referencia del abono y actualiza los datos de la pantalla. Si aún está en revisión o aprobado sin abono, abre el expediente en Mis reclamos. Consultar nunca ejecuta ni duplica un reembolso; éste conserva la confirmación administrativa. No hay espera artificial ni promesa de minutos.
