# Tres casos bancarios que puedes repetir

Este paquete prueba acciones desde React contra FastAPI y PostgreSQL de Docker: consulta del movimiento en el bot, contrato, solicitud, confirmación, operación y auditoría. Crea cuentas **Verificación** nuevas en cada ejecución, con contraseñas aleatorias. No necesita el dataset ni claves de Jev/LLM.

Los casos son reconstrucciones ficticias de familias de problemas analizadas en el EDA; **no son conversaciones auténticas del dataset**. Sus textos y resultados esperados están en [banking-cases.json](../tests/scenarios/banking-cases.json), con español, inglés y portugués.

Pase comprobado el 1 de octubre de 2026: **9/9 recorridos correctos**, 39 comprobaciones axe sin infracciones, cero errores JavaScript y registros financieros/de casos ajenos intactos durante la ejecución. Se corrigió además una cancelación de lectura que podía vaciar el panel al cambiar rápidamente los filtros de auditoría; dos pruebas de regresión cubren ese fallo. El informe local conserva tiempos y capturas; no es una medición de precisión de modelos.

| Caso | Acción del titular | Acción administrativa | Resultado que debe comprobarse |
| --- | --- | --- | --- |
| Cargo no reconocido: 185,00 MXN | Consultar movimiento, registrar reclamo y bloquear su tarjeta con contraseña y confirmación | Consultar auditoría y conversación | Tarjeta `blocked` tras recargar, folio NQ, saldo 1.500,00 MXN sin cambios. No se da por resuelto el reclamo. |
| Cobro incorrecto: 459,90 MXN | Consultar movimiento, registrar reclamo y solicitar devolución completa | Iniciar revisión, registrar motivo, confirmar con contraseña y aprobar | RF pendiente sin abono; después RF aprobada, un único CR de 459,90 MXN y saldo 1.959,90 MXN. El reintento de la misma decisión no duplica el abono. |
| Pago pendiente: 129,90 MXN | Consultar estado, registrar solicitud y pedir atención humana | Consultar auditoría y conversación | Devolución no elegible; solicitud `handed_off`, sin RF ni CR, saldo 1.500,00 MXN. El pago original continúa pendiente. |

## Ejecutar automáticamente

Desde la raíz del repositorio, con Docker Desktop iniciado y Node.js 24:

```powershell
npm ci
npm run setup
npm run docker:up
npm run test:cases
```

`setup` conserva `.env` si ya existe. `docker:up` conserva el volumen de PostgreSQL. Si el equipo ya está preparado, bastan los dos últimos comandos. No uses `docker compose down -v` para repetir estas pruebas.

El comando predeterminado ejecuta **tres casos × tres idiomas = nueve recorridos**. Cada recorrido tiene su propio titular. Se usa Edge instalado; si elegiste otro navegador Chromium compatible, configura `PLAYWRIGHT_CHANNEL` según tu instalación.

Para ver las acciones en ventanas del navegador, o ejecutar sólo un idioma:

```powershell
npm run test:cases -- --headed --locale=es
npm run test:cases -- --locale=en
npm run test:cases -- --locale=pt
```

Las ventanas cliente/administrador usan sesiones separadas. Ejecuta las pruebas bancarias en serie: una prueba simultánea u otra persona cambiando registros puede invalidar la comprobación de datos ajenos intactos.

El proceso devuelve código 0 sólo si pasa todo. Ante un fallo devuelve código distinto de 0 y conserva el informe con el paso fallido. No se borran registros ni se reanuda sobre un caso consumido: vuelve a ejecutar el comando para obtener un paquete nuevo.

## Hacer tú mismo los tres recorridos

Prepara un paquete **sin ejecutar sus acciones**:

```powershell
npm run test:cases:prepare
```

La consola muestra la ruta de `INICIAR.private.md`. Ese archivo contiene los accesos de tres clientes y un administrador, los movimientos y los textos de cada caso. Está en `.local/verification/cases/manual-<id>/`, excluido de Git. Para un paquete en otro idioma añade `-- --locale=pt` o `-- --locale=en`.

Abre [el banco](http://localhost:5180/). Usa una ventana/perfil separado para el administrador: dos pestañas del mismo perfil comparten la sesión. Cierra sesión al cambiar de cliente.

### 1. Cargo no reconocido y bloqueo

1. Entra con el cliente **bloqueo** del paquete. En Movimientos, abre su compra de 185,00 MXN y pulsa **Preguntar por este movimiento**. El bot debe mostrar el ID y el estado del movimiento propio.
2. En Servicios busca **cargo no reconocido**. Abre el servicio, elige ese movimiento, pega el texto del paquete y pulsa **Revisar datos**. Confirma los datos y registra la solicitud. Anota el folio NQ.
3. Ve a Tarjetas → **Bloquear tarjeta**. Introduce la contraseña de este cliente, marca la confirmación y confirma. Recarga: la tarjeta continúa bloqueada y no se pueden revelar sus datos.
4. Comprueba que el saldo sigue en **1.500,00 MXN**. El bloqueo protege la tarjeta local; no devuelve el cargo ni cierra el reclamo.
5. Como administrador, en Auditoría selecciona ese cliente y **Tarjeta bloqueada por su titular**. Verifica actor, tarjeta y fecha. Cambia a **Movimiento consultado por el asistente** para abrir la conversación.

### 2. Cobro incorrecto y devolución aprobada

1. Entra con el cliente **devolucion**. Consulta su movimiento de 459,90 MXN desde el bot. En Servicios busca **cobro incorrecto**, selecciona el movimiento, copia el texto y revisa/confirma la solicitud. Anota NQ.
2. En Mis solicitudes abre NQ. En Devolución comprueba importe y cuenta, marca **Solicito la revisión de este cargo para una devolución** y pulsa **Solicitar devolución**.
3. Debe aparecer **Devolución pendiente de aprobación**, con ID RF. El saldo continúa en **1.500,00 MXN**. Puedes buscar la solicitud por RF.
4. En la ventana del administrador abre ese NQ/RF. Pulsa **Iniciar revisión** y confirma. En la devolución elige aprobar, escribe el motivo de revisión, introduce la contraseña del administrador y marca la confirmación del abono. Confirma la decisión.
5. Como cliente recarga: **Devolución aprobada · abono registrado**, RF y CR visibles. El saldo es **1.959,90 MXN**, con un solo abono de 459,90 MXN. El cargo original conserva su ID e importe.
6. Vuelve a **Preguntar por este movimiento**: la respuesta debe incluir NQ, RF y CR actualizados. Recarga y recupera la conversación desde **Conversaciones**.
7. Como administrador consulta **Devolución solicitada**, **Solicitud en revisión** y **Devolución aprobada y abonada**. El solicitante debe ser el cliente y el aprobador, el administrador.

La política actual devuelve el cargo completo, una sola vez y a una cuenta vinculada al titular. Esta prueba no valida devoluciones parciales ni evidencia externa del comercio. El estado general del reclamo sigue siendo `in_review`; la aprobación tiene su estado propio.

### 3. Pago pendiente y derivación

1. Entra con el cliente **derivacion**. Abre el pago de 129,90 MXN y consulta al bot. Debe informar que está pendiente, sin afirmar que se completó ni recomendar repetirlo como si no existiera.
2. En Servicios busca **pago pendiente**, elige el movimiento y registra el texto del paquete tras revisar y confirmar. Anota NQ.
3. Abre NQ en Mis solicitudes. Debe decir que el movimiento **no admite devolución**; no aparece el botón de solicitarla.
4. Pulsa **Pedir atención humana** y **Confirmar derivación**. Recarga: debe decir **Enviada a atención**. Comprueba saldo intacto y ausencia de abono.
5. Como administrador filtra **Derivación solicitada** en Auditoría y abre la conversación del movimiento. Debe conservarse su contexto.

La derivación registra el estado y contexto; aún no asigna un especialista ni agenda una llamada. Es un desenlace de escalamiento, no una resolución financiera.

## Evidencia y tiempos

Cada ejecución automática genera una carpeta nueva en `.local/verification/cases/run-<id>/`:

- `report.html`: resultado por caso e idioma, pasos, tiempos, NQ/RF/CR y enlaces a capturas.
- `report.json`: mismas comprobaciones y verificación independiente de PostgreSQL, IDs de auditoría y recuentos de conversaciones/mensajes.
- Capturas de tarjeta/solicitud, aprobación/derivación, conversación, móvil de 390 px y auditoría.
- `credentials.private.json` e `INICIAR.private.md`: accesos privados del paquete automático, cuyas acciones ya fueron ejecutadas. Para practicar desde cero usa **prepare**.

`latest-run.json` y `latest-manual.json` apuntan al último informe y al último paquete manual. Se conservan los anteriores. Las contraseñas no se imprimen en consola ni aparecen en `report.html`/`report.json`; no se graban trazas de red con cookies o contraseñas.

Las acciones de negocio se hacen por la interfaz. Controles adicionales llaman a la API para comprobar que se rechazan tarjetas ajenas, acceso administrativo por un cliente, revelación de una tarjeta bloqueada y devolución de un pago pendiente. El reintento de aprobación reutiliza la decisión enviada por la interfaz para comprobar idempotencia. PostgreSQL comprueba los estados, saldos, un único abono, actores y conversaciones; un hash verifica que productos, tarjetas, movimientos, solicitudes y devoluciones de otros titulares siguen intactos.

Los tiempos son duraciones observadas de pasos automatizados en la máquina local. Incluyen navegación, espera de interfaz y, en algunos pasos, accesibilidad/capturas. **No miden latencia de Jev/Luna, tiempo humano de revisión ni SLA bancario**. Tres casos tampoco constituyen un benchmark representativo de resolución.

## Relación con el LAB y el flujo completo

El campo `intent` del archivo de escenarios es la etiqueta esperada para evaluar separadamente Jev. Los textos ES/EN/PT se pueden copiar al LAB; este comando no llama a proveedores ni mide su clasificación.

El banco consulta registros propios con respuestas guiadas. La conexión automática **mensaje → Jev → contrato → herramientas autenticadas → propuesta → confirmación → resultado** sigue pendiente. Estas pruebas dejan comprobados los componentes operativos que esa integración utilizará; no afirman que el modelo ejecute las operaciones.

Ver también [mapa del flujo completo](mapa-flujo-y-plan-pruebas.md), [acciones y permisos](acciones-problemas.md), [trazabilidad](trazabilidad-solicitudes.md) y [enrutamiento de Jev](enrutamiento-jev-herramientas.md).
