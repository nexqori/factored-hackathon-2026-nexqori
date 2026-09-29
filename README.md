# Nexqori

Base bancaria local con **React + TypeScript, FastAPI y PostgreSQL**. Identidad Terracota suave, español/inglés/portugués, acceso de cliente y administrador, productos, movimientos, servicios, solicitudes y agente de navegación.

Para incorporarte al desarrollo, comienza por [INICIO-EQUIPO.md](INICIO-EQUIPO.md): Docker, acceso, recorrido de revisión y mapa del código.

La base tiene autenticación y persistencia reales en el servidor local. Los datos son ficticios; no ejecuta operaciones bancarias. El asistente usa reglas guiadas, sin LLM ni operador humano conectado.

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

Puedes entrar con cualquiera de los dos identificadores y la misma contraseña. Los documentos conservan los ceros iniciales. Son identificadores locales: no se verifica un documento oficial ni se envía correo. Una cuenta registrada puede usar Gmail u otro proveedor; esta base aún no tiene registro público ni recuperación por email. La migración actualiza las direcciones iniciales anteriores y conserva contraseñas, sesiones y mensajes.

Nunca compartas `.env`; cada integrante genera el suyo. El seed se ejecuta sólo sobre una base vacía. Editar contraseñas en `.env` después del primer arranque no cambia los hashes existentes ni la clave del rol PostgreSQL. Para cambiar claves persistidas se requiere una migración de credenciales específica; evita desincronizar el archivo y la base.

```sh
docker compose ps
docker compose logs --tail=60 api
npm run docker:down
```

Detener contenedores conserva el volumen PostgreSQL. No uses opciones que borren volúmenes si quieres conservar solicitudes y conversaciones. Si el puerto 5180 está ocupado, libera el proceso correspondiente o cambia conjuntamente el puerto y los orígenes permitidos.

## Recorridos disponibles

- Login por correo o documento, cierre de sesión, roles de servidor y preferencia ES/EN/PT persistida.
- Selector de idioma accesible y Configuración con letra pequeña, mediana o grande guardada en la cuenta.
- Inicio, cuentas, tarjetas, movimientos con búsqueda/filtros y detalle por producto.
- Catálogo buscable de 20 servicios: telefonía, internet, cable, servicios públicos, transferencias, cuentas, tarjetas, préstamos, inversiones, seguros, efectivo y atención.
- Formularios específicos con cuenta propia, referencia, importe, revisión y confirmación; registran solicitudes con seguimiento, sin débito ni liquidación.
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

Lee [catálogo y evidencia](docs/catalogo-servicios.md), [acceso y conversaciones](docs/acceso-y-conversaciones.md), [arquitectura y API](docs/arquitectura.md), [agente y conexión futura de un modelo](docs/agente.md), [servicios basados en datos](docs/servicios-basados-en-datos.md) y [guía del dataset y EDA previo](docs/dataset.md). El contrato OpenAPI está en http://localhost:5180/api/openapi.json. El [objetivo](OBJETIVO-APP.md) es contexto de producto; las capacidades futuras no están implícitamente implementadas.

## Verificación

```sh
npm test
npm run build
docker compose exec api python -m pytest backend/tests -q
npm run test:ui
npm run test:experience
npm run test:services
```

La prueba UI requiere Docker activo y Microsoft Edge; para Chromium instalado con Playwright usa `PLAYWRIGHT_CHANNEL=chromium`. Crea solicitudes ficticias con marcador `UI verification` y conserva las capturas en `.local/verification/`. Las pruebas API usan bases SQLite temporales; el recorrido UI y la persistencia se verifican en PostgreSQL de Docker. Los resultados no equivalen a una certificación bancaria.

Para desarrollo de frontend con recarga automática, usa `npm run dev` y abre http://localhost:5173 con Docker activo. Vite reenvía `/api` al origen local de Docker. Reconstruye Docker después de modificar el backend.

## Skill compartible

La skill se descubre desde `.agents/skills/nexqori-brand/`. Para usarla en otro repositorio copia esa carpeta a `.agents/skills/` e invoca `$nexqori-brand`. Incluye paleta, SVG, tokens, criterios de interfaz, tres idiomas, stack y navegación permitida. No concede permisos para operar cuentas o publicar datos.

## GitHub y datos

Repositorio privado: [nexqori/nexqori](https://github.com/nexqori/nexqori). `.gitignore` y `.dockerignore` excluyen credenciales, dataset, documentos originales, entornos, dependencias y artefactos locales. Se comparten código, documentación, skill y agregados sin identificadores. La app utiliza fixtures propios; no carga las relaciones inconsistentes del dataset en cuentas de usuario.

No se añadió una licencia pública. Compartir dentro de la organización no cambia los permisos de uso del dataset del organizador. Antes de otro entorno se necesitan servicios de identidad, TLS, copias/restauración, observabilidad, políticas operativas e integraciones verificadas.
