# Catálogo de servicios Nexqori

Integración del 2 de octubre: [pagos y transferencias](pagos-y-transferencias.md), [consultas y PDF](consultas-y-documentos.md) y [continuidad de conversación](contexto-conversacion.md). Pagos y transferencias se guardan en Movimientos; documentos pedidos y trámites, en Mis solicitudes; problemas, en Mis reclamos.

Servicios permite buscar lo que se quiere hacer, el nombre de una empresa o una categoría. El catálogo contiene 20 entradas, con títulos, descripciones y sinónimos ES/EN/PT. No depende de descargar el dataset al ejecutar la app.

## Evidencia y decisiones

La consulta censal de `transactions` confirma estos nombres de comercio, sin exportar filas individuales:

| Nombre del origen, conservado en la app | Registros históricos | Servicio de interfaz |
| --- | ---: | --- |
| Empresa Telefónica | 51.464 | Pagar celular o teléfono |
| Internet Plus | 51.002 | Pagar internet |
| Cable TV | 51.430 | Pagar televisión |
| Servicios Públicos | 51.250 | Pagar servicios públicos |

Todos esos registros son de tipo `Purchase`, no `Payment`. De los 738.964 registros `Payment`, ninguno tiene nombre de comercio y 140.213 llevan categoría `Services`. El dataset respalda los nombres y categorías, pero no acredita convenios de recaudación, facturas, deudas ni transacciones ejecutables. Tampoco prueba que Empresa Telefónica distinga móvil/fijo o que Servicios Públicos tenga productos separados de agua, luz y gas. Esas palabras son sinónimos de descubrimiento hacia la categoría, no empresas adicionales. No se inventaron operadores como Telcel, Claro o Movistar.

La asociación del pedido “pagar celular” a telefonía es una decisión de producto solicitada por Bryan. Los campos, validaciones y recorrido de solicitud son diseño de Nexqori. El resto del catálogo se deriva de tipos de producto (cuentas, tarjetas, préstamos, inversión, seguro), operaciones (transferencia, retiro, depósito) y motivos de atención (cargo no reconocido, cobro indebido, problema con app, atención en sucursal y calidad de servicio). No se calculan ofertas, elegibilidad, intereses ni resolución a partir del dataset.

Fuente reproducible: [script de seis consultas agregadas](../scripts/analizar_catalogo_nexqori.py), [SQL, resultados y comprobaciones](../notebooks/servicios_nexqori/catalog_evidence.json), y [análisis general](servicios-basados-en-datos.md). Se recorre la caché censal local en modo sólo lectura; todos los estados históricos se incluyen. Las fechas del origen no declaran zona horaria. El script verifica que cada valor fuente de las 20 entradas exista y que el total transaccional concuerde con 4.425.008. Los registros son del dataset sintético del organizador, no clientes del entorno local.

## Recorrido de producto

1. Buscar “pagar celular”, “phone bill”, “pagar celular”, “Internet Plus” u otra necesidad. La búsqueda elimina diferencias de mayúsculas y acentos y admite sinónimos y errores cercanos. Los filtros limitan a la categoría seleccionada; sin resultados se puede limpiar y volver al catálogo.
2. Elegir servicio. Las consultas de cuentas, tarjetas y movimientos abren las vistas propias. Las facturas buscan recibos propios por número/código; las transferencias buscan otra cuenta Nexqori por referencia y muestran el destinatario antes del importe. Los reclamos permiten elegir un movimiento propio; los casos de cargo/cobro/pago lo exigen. Las consultas de producto/atención solicitan un detalle.
3. Revisar y confirmar. Facturas y transferencias generan movimientos y comprobante; trámites como crédito generan solicitudes; problemas abren reclamos. Un mensaje del asistente no confirma la operación.
4. Consultar Movimientos para pagos/transferencias; Mis solicitudes para trámites y PDF; Mis reclamos para evolución de problemas.

La interfaz utiliza lenguaje de producto y no muestra etiquetas de demo. Cada recorrido usa su confirmación y resultado. El comprobante de pago sólo aparece tras guardar el débito en PostgreSQL; no acredita liquidación con un proveedor externo.

## Contrato e implementación

- Fuente única de definiciones: `backend/service_catalog.json`. Incluye procedencia, traducciones y tipo de recorrido. API y validación de navegación del frontend comparten ese registro; agregar una entrada requiere validación y reconstrucción. No se implementó un CMS ni un panel para crear convenios.
- `GET /api/services?q=&category=&locale=` y `GET /api/services/{id}` exigen sesión de cliente. Exponen únicamente campos de presentación, no registros del dataset.
- `POST /api/services/{id}/requests`: admite trámites y reclamos; rechaza tipos bill/transfer para impedir solicitudes financieras falsas. Exige cliente, origen, CSRF, confirmación, ID registrado y campos estrictos. El servidor deriva categoría, empresa y motivo desde el catálogo, no del cliente.
- Importes en unidades menores enteras, de 1 a 100.000.000 (0,01–1.000.000 MXN): límite técnico de captura, no límite bancario acreditado. No se convierten monedas. Los formatos regionales con coma/punto se convierten sin aritmética decimal flotante en el frontend.
- Facturas y transferencias requieren una cuenta propia de tipo cuenta/ahorro en MXN. La FK compuesta de cuenta/titular refuerza el control. Tarjetas y productos ajenos se rechazan. El servidor verifica referencia, recibo y destinatario en sus registros locales. No hay recaudador externo. [Contratos de pagos y transferencias](pagos-y-transferencias.md).
- Un reintento idéntico con la misma clave devuelve la misma referencia y no duplica auditoría. Cambiar datos con la misma clave devuelve conflicto. Los reclamos conservan la regla existente de una solicitud por movimiento.
- `requests` incorpora `catalog_service_id`, `source_product_id` y `service_data`. La migración `c83d71a6e520` conserva los casos previos con esos campos vacíos; no altera mensajes ni saldos.
- El asistente reconoce servicios concretos de facturación y propone un comando de navegación. `serviceId` debe existir en el registro y la ruta debe coincidir exactamente. La conversación no envía el formulario.

La voz queda fuera de esta implementación. La base no instala motores de transcripción o síntesis y no usa el micrófono.

## Comprobación

`backend/tests/test_catalog.py` verifica el registro, búsqueda, localización, permisos, campos, titularidad, FK, idempotencia, ausencia de débito y navegación. `src/catalog.test.ts` prueba conversión monetaria y rutas permitidas. `npm run test:services` recorre búsquedas y confirmación en Docker/PostgreSQL, historial, vista admin, ES/EN/PT, móvil y accesibilidad automatizada. Los resultados y capturas quedan en `.local/verification/`.
