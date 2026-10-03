# Cinco usuarios para pruebas UX

Este paquete crea cinco clientes persistentes en PostgreSQL local. Cada uno tiene cuenta, ahorro, tarjeta activa, cinco movimientos y cuatro recibos. Inician sin conversaciones, reclamos, solicitudes ni devoluciones. El caso de teléfono tiene un débito y un comprobante pendientes para que se pueda investigar sin repetir el pago.

Las personas, contraseñas y operaciones son ficticias. Las familias de problemas corresponden a los contratos del proyecto y al [análisis del dataset](servicios-basados-en-datos.md). Los nombres Empresa Telefónica, Internet Plus, Cable TV y Servicios Públicos proceden de la [evidencia agregada del catálogo](../notebooks/servicios_nexqori/catalog_evidence.json). No se importan clientes ni transcripciones del dataset. Los recibos no prueban un convenio de recaudación.

## Preparar el grupo

1. Actualiza el código y reconstruye la API local con `docker compose up --build -d api web`. Conserva el volumen de PostgreSQL.
2. Ejecuta el comando explícito:

```powershell
node scripts/prepare-ux-users.mjs --confirm-local --pack=equipo-ux
```

3. Abre `.local/ux-users/equipo-ux/INICIAR.private.md`. Allí aparecen correos, documentos de acceso, contraseñas aleatorias, referencias de cuenta, movimientos y recibos de cada persona. No publiques esa carpeta.
4. Inicia sesión en `http://localhost:5180` con el cliente del caso que quieras probar. Abre **Nueva conversación** y usa la frase de la tabla o tu propia descripción.

El comando escribe primero el manifiesto privado de contraseñas y después crea los registros en PostgreSQL. Si se pierde la respuesta, repetir el comando conserva las identidades y las contraseñas. Una nueva ejecución con el mismo nombre no reinicia saldos, tarjetas, movimientos, conversaciones ni reclamos. Para otro grupo limpio, usa otro valor de `--pack`; no borres el volumen ni reutilices la cuenta de Andrea.

El módulo exige el indicador de verificación local y la base `nexqori` del servicio `db` de Compose. Compara una huella de los registros existentes antes y después de preparar el paquete. Si encuentra un paquete incompleto, registros ajenos con esas identidades o un error de integridad, revierte la inserción; no intenta repararlo eliminando datos.

## Matriz de casos

| Persona | Datos preparados | Frase inicial sugerida | Qué comprobar |
| --- | --- | --- | --- |
| Camila Torres | Cargo de tarjeta por 185,00 MXN en Empresa Telefónica y otro movimiento propio para cambiar la selección. | «No reconozco este cobro de 185 pesos. Tengo mi tarjeta conmigo y quiero que lo revisen.» | Confirmar o cambiar el movimiento. El resumen debe referirse al elegido. Registrar un reclamo conserva el relato; no bloquea ni devuelve dinero automáticamente. |
| Diego Medina | Cargo de tarjeta por 459,00 MXN en Internet Plus. La frase declara que esperaba 299,00 MXN. | «Me cobraron 459 pesos por internet y esperaba pagar 299 pesos. Quiero revisar la diferencia.» | Distinguir el importe del banco y lo declarado. Si falta información, pedirla. Registrar para revisión; una devolución requiere el flujo administrativo separado. |
| Valeria Rojas | Débito de 299,00 MXN y comprobante telefónico pendientes. El importe ya se descontó; ese recibo no permite otro pago por la misma deuda. | «Pagué 299 pesos de teléfono. El dinero se descontó, pero el pago sigue pendiente. ¿Puedes revisar qué pasó?» | El bot informa pendiente sin inventar una confirmación del operador. Consultar y registrar un reclamo no vuelve a descontar el dinero ni completa el pago. |
| Lucas Costa | Intento de pago rechazado sin débito y recibos abiertos. La frase describe un cierre de la app y dos intentos previos. | «La app se cierra cuando intento pagar el teléfono. Ya reinicié la app y el teléfono y vuelve a pasar.» | Reunir síntoma e intentos; solicitar evidencia adicional o atención cuando sea necesario. El movimiento rechazado no prueba por qué se cerró la app. No se generan logs ficticios de una caída real. |
| Sofía Vega | Movimientos del mes calendario anterior y registros recientes. El periodo exacto aparece en la guía privada. | «Quiero consultar los movimientos del mes pasado y obtener un estado de cuenta en PDF.» | Conservar el periodo al abrir Movimientos y preparar el PDF. Revisar los parámetros antes de generar, recuperar el mismo archivo desde el historial o Mis documentos y no crear un reclamo por una consulta. Mis solicitudes conserva acceso por compatibilidad. |

Los mensajes también están definidos en inglés y portugués en [ux_scenarios.json](../backend/ux_scenarios.json). Cada cliente inicia en español y puede cambiar de idioma. Las edades y la experiencia digital varían para revisar la presentación y la asistencia, sin atribuir capacidad o discapacidad a una edad.

## Datos y límites

- La cuenta tiene un saldo de apertura de referencia de 1.500,00 MXN más los movimientos completados o pendientes preparados sobre esa cuenta. Los intentos rechazados no lo reducen. El ahorro empieza en 640,00 MXN; los movimientos de tarjeta se muestran en su producto independiente.
- Los movimientos anteriores incluyen un ingreso mensual ficticio y cargos de servicios. Las fechas se calculan una vez al crear el manifiesto, usando America/Mexico_City, y permanecen iguales al repetirlo.
- Cada persona tiene dos referencias telefónicas, internet y televisión. Los números concretos se guardan en la guía privada. Algunos recibos permiten abonos; televisión y la primera línea sólo admiten el total.
- El pago pendiente es un escenario controlado del libro local, sin recaudador ni temporizador. No se resuelve al esperar o reiniciar. Véase [pagos y transferencias](pagos-y-transferencias.md).
- El script no ejecuta Jev ni LLM. Conversar manualmente con el bot utiliza los proveedores que tenga configurados la app. La clasificación real puede pedir más datos; la matriz describe criterios de aceptación, no respuestas forzadas.
- Las referencias propias permiten probar transferencias entre dos integrantes del paquete. Sigue siendo necesario comprobar al destinatario, revisar el importe y confirmar; el texto del chat no autoriza la transferencia.

## Repetir la validación del generador

```powershell
.venv-app/Scripts/python.exe -m pytest backend/tests/test_ux_fixtures.py -q
node --check scripts/prepare-ux-users.mjs
```

Estas pruebas usan SQLite aislado. Comprueban los cinco perfiles, la coherencia del pendiente, los meses, las traducciones, el rechazo de manifiestos alterados, el rollback y la repetición sin restablecer actividad posterior. La creación manual del paquete se hace contra PostgreSQL local con el comando de preparación anterior.

## Usuarios de la regresión automática

`npm run test:ui`, `npm run test:experience` y `npm run test:services` crean por defecto un paquete aparte llamado `verificacion-ui-<identificador>`. Usan a Camila de ese paquete para crear conversaciones, cambiar preferencias y registrar los casos de comprobación. No usan Andrea ni los cinco clientes de `equipo-ux`. Las lecturas administrativas conservan la cuenta configurada en `.env`.

Al comenzar, cada comando muestra la ruta privada `verificationUserFile`. Para ejecutar varias pruebas sobre el mismo grupo, asigna esa ruta a `NEXQORI_TEST_USER_FILE` antes del siguiente comando y retira la variable al terminar. El archivo debe ser `records.private.json` de un paquete `verificacion-ui`; el helper rechaza `equipo-ux` y otros titulares. No publiques el manifiesto ni las contraseñas.

La validación del helper se puede ejecutar sin Docker ni proveedores:

```powershell
npm test -- scripts/verification-user.test.mjs
```
