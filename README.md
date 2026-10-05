# Nexqori

Integración vigente: [pagos y transferencias](docs/pagos-y-transferencias.md), [consultas y PDF](docs/consultas-y-documentos.md) y [continuidad de conversación](docs/contexto-conversacion.md). Pagos y transferencias se guardan en Movimientos; PDF, en Mis documentos; trámites, en Mis solicitudes; problemas, en Mis reclamos.

Base bancaria local con **React + TypeScript, FastAPI y PostgreSQL**. Identidad Terracota suave, español/inglés/portugués, acceso de cliente y administrador, productos, movimientos, servicios, solicitudes y agente de navegación.

Para incorporarte al desarrollo, comienza por [INICIO-EQUIPO.md](INICIO-EQUIPO.md): Docker, acceso, recorrido de revisión y mapa del código.

Para probar acciones completas, usa la [guía de tres casos reproducibles](docs/pruebas-tres-casos.md): `npm run test:cases` verifica bloqueo, devolución aprobada y derivación en ES/EN/PT; `npm run test:cases:prepare` deja usuarios nuevos para repetirlos manualmente.

La base tiene autenticación y persistencia en PostgreSQL local. Los pagos, transferencias, bloqueos y devoluciones tienen efectos en sus registros ficticios; no hay liquidación externa. El chat conecta Jev y Luna cuando se configuran sus claves privadas; conserva un recorrido guiado si esa conexión no está disponible. No hay operador humano conectado. Las llamadas requieren claves propias y arranque explícito con `compose.voice.yaml`; consulta [voz y límites](docs/voz-gpt-live.md).

El [LAB independiente](experiments/intent-lab/README.md), en localhost:5190, sí conecta Jev y GPT-6 Luna high para comparar clasificación y probar respuestas guiadas por contrato. La base del banco incorpora registro adulto, preferencias de experiencia, auditoría administrativa, texto pegado y presentación visual de llamada. Consulta la [guía de estos recorridos](docs/registro-auditoria-y-conversacion.md).

Los contratos se activan sólo para problemas; consultas y servicios tienen recorridos separados. El banco permite bloquear una tarjeta propia y solicitar devolución de un cargo completado; un administrador debe revisar y aprobar el abono. [Acciones, permisos y pruebas](docs/acciones-problemas.md). Son efectos persistentes en PostgreSQL local, sin emisor ni liquidación externa.

## Arranque local

Necesitas Docker Desktop iniciado (contenedores Linux) y Node.js 24 con npm. Desde la raíz:

```sh
npm ci
npm run setup
npm run docker:up
```

Abre **http://localhost:5180**. Sólo ese puerto está publicado y escucha en 127.0.0.1. El dataset del hackathon no es necesario para ejecutar la app.

El setup genera contraseñas aleatorias en `.env` y conserva el archivo si ya existe. Abre ese archivo local para obtener la clave correspondiente:

| Correo inicial | Documento inicial | Rol | Variable con su contraseña |
| --- | --- | --- | --- |
| andrea@nexqori.com | 00000001 | Cliente | CUSTOMER_PASSWORD |
| admin@nexqori.com | 00000002 | Administrador | ADMIN_PASSWORD |
| mateo@nexqori.com | 00000003 | Segundo cliente para probar aislamiento | SECOND_CUSTOMER_PASSWORD |

Puedes entrar con cualquiera de los dos identificadores y la misma contraseña. Los documentos conservan los ceros iniciales. Son identificadores locales: no se verifica un documento oficial ni se envía correo. Crear mi perfil admite Gmail u otro proveedor; aún no hay verificación ni recuperación por email. La migración actualiza las direcciones iniciales anteriores y conserva contraseñas, sesiones y mensajes.

Nunca compartas `.env`; cada integrante genera el suyo. El seed crea clientes sólo en una base vacía y añade referencias/recibos locales faltantes sin reponer saldos ni recibos pagados. Editar contraseñas en `.env` después del primer arranque no cambia los hashes existentes ni la clave del rol PostgreSQL. Para cambiar claves persistidas se requiere una migración de credenciales específica; evita desincronizar el archivo y la base.

```sh
docker compose ps
docker compose logs --tail=60 api
npm run docker:down
```

Detener contenedores conserva el volumen PostgreSQL. No uses opciones que borren volúmenes si quieres conservar solicitudes y conversaciones. Si el puerto 5180 está ocupado, libera el proceso correspondiente o cambia conjuntamente el puerto y los orígenes permitidos.

## Bryan y administración para la demo

Los usuarios y casos se guardan en PostgreSQL. El código compartido prepara a Bryan con pesos mexicanos, un recibo de 459 MXN frente a un plan de 299 MXN y una compra de 2.700 MXN frente a un promedio de 600 MXN. No copia conversaciones ni reclamos de Camila.

Con Docker iniciado y la API actualizada:

```sh
node scripts/prepare-bryan-demo.mjs --confirm-local
node scripts/demo-access.mjs --confirm-local
```

Abre `.local/ux-users/bryan-demo/ACCESOS.private.md`: contiene el correo, documento y contraseña de Bryan y de `admin@nexqori.com` (documento `00000002`). El exportador verifica las contraseñas contra la base sin cambiarlas. Cada instalación conserva claves propias; la guía y `.env` quedan fuera de Git. Si una contraseña cambió después del setup, el comando informa la diferencia y no sobrescribe el acceso.

La preparación repetida conserva el correo personalizado y la actividad de Bryan. No reinicia pagos ni reclamos. Usa otro perfil del navegador para entrar al [panel administrativo](http://localhost:5180/admin/complaints) mientras pruebas como cliente. Mensajes y pasos: [demo de Bryan](docs/demo-bryan.md). La devolución requiere un cargo completado, confirmación del cliente y aprobación administrativa; un pago pendiente no se devuelve ni cancela automáticamente.

## Recorridos disponibles

- Login por correo o documento, cierre de sesión, roles de servidor y preferencia ES/EN/PT persistida.
- Selector de idioma accesible y Configuración con letra pequeña, mediana o grande guardada en la cuenta.
- Inicio, cuentas, tarjetas, movimientos con búsqueda/filtros y detalle por producto.
- Catálogo buscable de 20 servicios: telefonía, internet, cable, servicios públicos, transferencias, cuentas, tarjetas, préstamos, inversiones, seguros, efectivo y atención.
- Facturas por número/código: importe fijado por el recibo, pago total o parcial permitido, revisión, débito y comprobante en Movimientos. Transferencias entre clientes Nexqori con destinatario validado y dos asientos atómicos. Sin liquidación externa.
- PDF con cuenta/período recuperados de la conversación, revisión antes de generar y descarga persistente en Mis documentos.
- Solicitudes con confirmación, referencia, idempotencia, estado y solicitud de atención.
- Panel admin para usuarios, cola, inicio de revisión y auditoría.
- Agente: “Llévame a transferencias”, “Show my cards”, “Abrir empréstimos”. Navega por rutas permitidas, consulta el saldo propio y prepara un formulario; no ejecuta operaciones.
- Conversaciones independientes: empieza una nueva o retoma una desde el historial. Al volver a entrar, los mensajes antiguos se abren sólo si eliges una conversación.


## Estructura y documentación

| Ruta | Contenido |
| --- | --- |
| src/ | React, rutas, componentes, tokens y diccionarios ES/EN/PT. |
| backend/ | FastAPI, permisos, modelos, fixtures, herramientas, migraciones y pruebas. |
| docker/ y compose.yaml | PostgreSQL, API y frontend con un origen local. |
| .agents/skills/nexqori-brand/ | Skill portable con identidad, idiomas, stack y reglas del agente. |
| notebooks/SERVICIOS_NEXQORI.ipynb | Análisis ejecutado con tablas, gráficos y denominadores. |
| notebooks/servicios_nexqori/ | Agregados, consultas y comprobaciones del análisis de servicios. |

Lee [catálogo y evidencia](docs/catalogo-servicios.md), [acceso y conversaciones](docs/acceso-y-conversaciones.md), [arquitectura y API](docs/arquitectura.md), [agente y contexto conversacional](docs/agente.md), [servicios basados en datos](docs/servicios-basados-en-datos.md) y [guía del dataset y EDA previo](docs/dataset.md). El contrato OpenAPI está en http://localhost:5180/api/openapi.json. El [objetivo](OBJETIVO-APP.md) es contexto de producto; las capacidades futuras no están implícitamente implementadas.

## Verificación

```sh
npm test
npm run build
docker compose exec api python -m pytest backend/tests -q
npm run test:ui
npm run test:experience
npm run test:services
npm run test:banking
```

La prueba UI requiere Docker activo y Microsoft Edge; para Chromium instalado con Playwright usa `PLAYWRIGHT_CHANNEL=chromium`. Crea solicitudes ficticias con marcador `UI verification` y conserva las capturas en `.local/verification/`. Las pruebas API usan bases SQLite temporales; el recorrido UI y la persistencia se verifican en PostgreSQL de Docker. Los resultados no equivalen a una certificación bancaria.

Para desarrollo de frontend con recarga automática, usa `npm run dev` y abre http://localhost:5173 con Docker activo. Vite reenvía `/api` al origen local de Docker. Reconstruye Docker después de modificar el backend.

## Módulo de seguridad

La rama de Santiago `security-lab-module` se incorpora como [módulo aislado](security-lab/README.md), con interfaz en `http://localhost:5200`. El editor de atención conserva `5190`. Su Compose usa otra base y una copia del banco como objetivo; no reutiliza clientes, claves ni conversaciones del banco principal. Consulta [integración y límites](docs/integracion-equipo.md).

## Skill compartible

La skill se descubre desde `.agents/skills/nexqori-brand/`. Para usarla en otro repositorio copia esa carpeta a `.agents/skills/` e invoca `$nexqori-brand`. Incluye paleta, SVG, tokens, criterios de interfaz, tres idiomas, stack y navegación permitida. No concede permisos para operar cuentas o publicar datos.

## GitHub y datos

Repositorio privado: [nexqori/nexqori](https://github.com/nexqori/nexqori). `.gitignore` y `.dockerignore` excluyen credenciales, dataset, documentos originales, entornos, dependencias y artefactos locales. Se comparten código, documentación, skill y agregados sin identificadores. La app utiliza fixtures propios; no carga las relaciones inconsistentes del dataset en cuentas de usuario.

No se añadió una licencia pública. Compartir dentro de la organización no cambia los permisos de uso del dataset del organizador. Antes de otro entorno se necesitan servicios de identidad, TLS, copias/restauración, observabilidad, políticas operativas e integraciones verificadas.

## AWS y HTTPS

Para una instancia EC2 con Docker Compose y subdominio, usa la [guía de despliegue](docs/despliegue-aws-compose.md). `compose.cloud.yaml` añade certificado automático, origen HTTPS y cookies seguras; combina `compose.voice.yaml` para conservar las llamadas. La configuración y los datos privados se preparan en el servidor.
