# Fuentes de tarifas y cambios de precio

Nexqori puede consultar una fuente de precios construida para las pruebas y agregar esa información al contexto de un movimiento que tenga el mismo servicio, proveedor y plan. La publicación aporta una pista; no demuestra que el cargo del cliente sea correcto y no cambia pagos, saldos, tarjetas ni reclamos.

## Caso disponible

| Campo | Valor construido |
| --- | --- |
| Empresa | Empresa Telefónica |
| Proveedor interno | `empresa-telefonica` |
| Servicio | `phone-bill` |
| Plan | `telefono-esencial` / Teléfono Esencial |
| Tarifa habitual | MXN 299,00 al mes |
| Nueva tarifa | MXN 459,00 al mes |
| Inicio de la nueva tarifa | 1 de octubre de 2026 |
| Fuente | `/api/provider-examples/phone-bill/telefono-esencial` |

El nombre del comercio aparece en el dataset. El plan, la publicación y los importes 299→459 son construidos. No son avisos reales de ese comercio ni una integración con una operadora de telefonía. El endpoint no recibe ni contiene nombres de clientes, teléfonos, referencias bancarias, credenciales o contratos.

El caso de Camila incorpora el proveedor y el plan a los comprobantes construidos. La búsqueda del contexto exige esa relación explícita; una coincidencia aproximada de nombre o importe no vincula al cliente con una tarifa.

## Probar la detección

1. En administración, abre **Cambios de tarifas** y busca «teléfono» o «Empresa Telefónica».
2. Marca la confirmación y pulsa **Publicar precio habitual · $299**.
3. Pulsa **Revisar cambios** para guardar la lectura inicial. La primera lectura establece una referencia; no se presenta como un cambio detectado.
4. Entra con Camila y consulta el cobro de teléfono de MXN 459. El historial bancario permite ver la diferencia frente a sus pagos anteriores.
5. Desde administración, publica **aumento · $459**. El precio publicado cambia; la última consulta permanece visible hasta que el lector vuelva a consultar.
6. Pulsa **Revisar cambios** o espera el intervalo configurado. Abre de nuevo el detalle del movimiento o inicia una nueva conversación con ese movimiento vinculado para leer el contexto actualizado. El lector detecta la publicación y conserva ambas observaciones.
7. Revisa la respuesta: debe mencionar la tarifa publicada, el precio anterior y la fecha de vigencia, y pedir contrastar contrato, período y conceptos. Un pago pendiente sigue pendiente.

Publicar el precio habitual otra vez permite repetir el ejemplo. No reinicia los movimientos de Camila ni reemplaza el botón privado de reinicio. Las respuestas y los flujos ya terminados conservan el contexto de su ejecución; un mensaje en un flujo ya registrado no garantiza una lectura nueva. Usa el detalle del movimiento o una nueva conversación vinculada para comprobar la última publicación.

## Modelo de lectura

`backend/provider_updates.py` separa tres acciones:

- **Publicar:** modifica sólo la fuente controlada mediante una operación de administrador, confirmación y CSRF.
- **Consultar:** lee el documento versionado, verifica su esquema, registra fecha y hash y compara con la última observación.
- **Relacionar:** usa el recibo del mismo titular para buscar servicio/proveedor/plan/moneda exactos y comprobar las fechas.

El transporte interno invoca el mismo documento que sirve el endpoint. No realiza HTTP hacia localhost ni acepta URLs introducidas por el usuario. No hay rastreo libre, resolución DNS, redirecciones ni conexiones a direcciones privadas. Una integración externa futura debe incorporar un adaptador específico, lista de destinos permitidos y límites de red; esta implementación no acepta una URL genérica como sustituto.

La fecha del cobro no equivale al período facturado. El contexto comprueba también `phone_bills.period`: una factura de septiembre pagada en octubre no hereda automáticamente la tarifa de octubre. Aun con coincidencia, `customerContractVerified` y `authorizesAction` permanecen en `false`.

Una observación conserva proveedor, servicio, plan, importe, moneda, periodicidad, precio anterior anunciado, vigencia, publicación, lectura, revisión, URL de origen, hash y procedencia `controlled_example`. No conserva instrucciones ni HTML de una página. Un esquema inesperado produce `unavailable`; la última lectura queda identificada como historial, no como precio vigente.

## API y configuración

| Ruta | Acceso y efecto |
| --- | --- |
| `GET /api/provider-examples/phone-bill/telefono-esencial` | Fuente pública controlada, sólo cuando está habilitada. No incluye datos de usuarios. |
| `GET /api/admin/provider-updates?q=teléfono` | Administrador; lista, búsqueda, estado e historial. |
| `POST /api/admin/provider-updates/example` | Administrador + CSRF + `{"preset":"usual" o "increase","confirmed":true}`; publica la tarifa elegida. |
| `POST /api/admin/provider-updates/refresh` | Administrador + CSRF; consulta y compara. Cuerpo `{}`. |

Variables del servidor:

```dotenv
PROVIDER_EXAMPLES_ENABLED=true
PROVIDER_EXAMPLES_CACHE=/app/provider-updates/state.json
PROVIDER_EXAMPLES_WATCH_SECONDS=30
```

La función está desactivada por defecto fuera de la configuración explícita de las pruebas. Un intervalo `0` desactiva el temporizador: siguen disponibles la consulta manual y la lectura al revisar un movimiento vinculado. El temporizador tiene un mínimo de 30 segundos y sólo consulta el endpoint controlado en el propio proceso.

La caché conserva hasta 20 observaciones distintas, con escritura de archivo temporal y reemplazo. El volumen configurado permite recuperarlas después de reiniciar Docker. Sin ruta de caché, se conservan sólo en memoria. Un fallo de almacenamiento aparece en administración; no se presenta como persistencia confirmada. El diseño corresponde al único proceso de la API local; no coordina varios workers ni reemplaza un registro de publicaciones para producción.

Integración en `create_app`: crear `ProviderUpdates.from_env()`, guardar en `app.state.provider_updates`, configurar `app.state.sessions.configure(info={'provider_updates': runtime})`, registrar `provider_updates_router()` y enlazar `start()`/`shutdown()` al ciclo de vida. El helper `price_context(db, transaction)` consulta sólo un `BillPayment` y `PhoneBill` del titular del movimiento. `provider_context_text` genera la explicación ES/EN/PT de forma determinista; no transmite registros al modelo ni a una empresa externa.

Las publicaciones y consultas manuales registran `provider_example_published` y `provider_source_checked` con el administrador como actor. Las revisiones automáticas quedan en el historial de observaciones de la fuente. Ninguna de estas acciones es una operación bancaria.

## Lo que permite afirmar el dataset

La evidencia agregada existente registra 51.464 compras con comercio «Empresa Telefónica» y 51.002 con «Internet Plus». También hay 12.194 casos clasificados como «Cobro indebido». Véanse [evidencia del catálogo](../notebooks/servicios_nexqori/catalog_evidence.json) y el [EDA integral](../notebooks/EDA_PROBLEMAS.ipynb).

La tabla de transacciones no contiene identificador de plan, condiciones del contrato ni publicaciones de tarifas. Variaciones de importes entre meses mezclan clientes, consumo y conceptos y no demuestran un cambio de precio. En esta revisión no se encontró un aviso verificable que explique este ejemplo. Por eso la publicación 299→459 se identifica como construida y no se atribuye a una compañía real.

Una comprobación adicional en la base EDA de sólo lectura encontró compras de «Empresa Telefónica» en ARS, COP y USD, sin MXN. Los pesos mexicanos pertenecen a la configuración construida de la app; no son una conversión ni un importe extraído de esos registros.

Como referencia para un adaptador futuro, [Movistar publica un aviso para PRO 13](https://movistar.com.mx/aviso/plan-pro-13-a) que declara renta de MXN 239 a MXN 249 desde el 16 de junio de 2026. Se consultó el 3 de octubre de 2026. Una lectura directa desde este entorno respondió HTTP 403; ese sitio **no está integrado ni se presenta como fuente consultada por la app**. El aviso tampoco demuestra que un cliente de Nexqori tenga ese plan.

## Comprobación

```powershell
.\.venv-app\Scripts\python.exe -m pytest backend/tests/test_provider_updates.py -q
```

Las pruebas cubren permisos, CSRF/origen, confirmación, búsqueda, publicación y detección separadas, deduplicación, persistencia acotada, fallo de esquema, coincidencia exacta de plan y moneda, período facturado, separación entre titulares y ausencia de cambios bancarios. No prueban una integración externa real ni justifican resolver automáticamente un reclamo.
