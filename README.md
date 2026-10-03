# Nexqori

Chat conectado a `chat-agente` mediante la sesión autenticada: [flujo, activación y límites](docs/agente.md). Arranca con reglas locales; Jev + OpenAI se habilitan explícitamente. Se conservan el [baseline de clasificación](docs/clasificacion-intenciones.md) y el [protocolo de evaluación](docs/evaluacion-intenciones.md).

Análisis local para intenciones: [notebook Python](notebooks/intentions/INTENTIONS_EDA.ipynb), [lectura HTML](notebooks/intentions/INTENTIONS_EDA.html) e [instrucciones y resultados](notebooks/intentions/README.md). La fuente se detecta en la carpeta hermana `nexqori-dataset`; los derivados individuales permanecen excluidos de Git.

Base bancaria local con **React + TypeScript, FastAPI y PostgreSQL**. Identidad Terracota suave, español/inglés/portugués, acceso de cliente y administrador, productos, movimientos, servicios, solicitudes y chat de consulta.

La base tiene autenticación y persistencia reales en el servidor local. Los datos son ficticios; no ejecuta operaciones bancarias. El chat sólo consulta: no cambia registros, permisos ni abre formularios. La atención humana utiliza una bandeja interna temporal, previa confirmación del cliente.

## Arranque local

Necesitas Docker Desktop iniciado (contenedores Linux) y Node.js 24 con npm. Desde la raíz:

```sh
npm ci
npm run setup
npm run docker:up
```

Abre **http://localhost:5180**. Web escucha en 127.0.0.1:5180; PostgreSQL está publicado en 127.0.0.1:5433 (internamente db:5432). El dataset del hackathon no es necesario para ejecutar la app.

El setup genera contraseñas aleatorias en `.env` y conserva el archivo si ya existe. Abre ese archivo local para obtener la clave correspondiente:

| Cuenta inicial | Rol | Variable con su contraseña |
| --- | --- | --- |
| andrea@nexqori.local | Cliente | CUSTOMER_PASSWORD |
| admin@nexqori.local | Administrador | ADMIN_PASSWORD |
| mateo@nexqori.local | Segundo cliente para probar aislamiento | SECOND_CUSTOMER_PASSWORD |

Nunca compartas `.env`; cada integrante genera el suyo. El seed se ejecuta sólo sobre una base vacía. Editar contraseñas en `.env` después del primer arranque no cambia los hashes existentes ni la clave del rol PostgreSQL. Para cambiar claves persistidas se requiere una migración de credenciales específica; evita desincronizar el archivo y la base.

```sh
docker compose ps
docker compose logs --tail=60 api
npm run docker:down
```

Detener contenedores conserva el volumen PostgreSQL. No uses opciones que borren volúmenes si quieres conservar solicitudes e historial anterior. Las nuevas conversaciones del chat son temporales y no se guardan en PostgreSQL. Si el puerto 5180 está ocupado, libera el proceso correspondiente o cambia conjuntamente el puerto y los orígenes permitidos.

## Chat conectado a chat-agente

`POST /api/assistant` usa `backend/chat_gateway.py` → `ChatAgent` → códigos 2, 3, 4 y 5. React sólo envía texto, idioma y referencias de conversación/mensaje. El servidor toma automáticamente `nexqori_session` de la cookie HttpOnly, obtiene el usuario y valida CSRF, rol y vigencia. **No configurar NEXQORI_SESSION_TOKEN ni user_id en el frontend.**

Configuración inicial local (sin proveedores):

```dotenv
CHAT_AGENT_MODE=rules
CHAT_AGENT_ALLOW_EXTERNAL_DATA=false
```

Para activar el orquestador con Jev y GPT-6 Luna, después de autorizar el envío de los datos descritos abajo, configurar el `.env` raíz:

```dotenv
CHAT_AGENT_MODE=agent
CHAT_AGENT_ALLOW_EXTERNAL_DATA=true
TYPESAFE_API_KEY=<clave privada TypeSafe>
OPENAI_API_KEY=<clave privada OpenAI>
```

Luego, desde la raíz, `docker compose up -d --build api web`. No hace falta ejecutar `py -m nexqori_chat`, copiar cookies ni publicar otro puerto. La API usa su misma `DATABASE_URL` de Compose y el lector trabaja contra `db:5432`; `PGPORT=5433` sólo corresponde a programas fuera de Docker. Las claves por sí solas no activan proveedores. Las variables `INTENT_*` pertenecen al baseline experimental anterior y no controlan este puente.

**Datos enviados al activar proveedores:** Jev recibe contexto conversacional y reglas para los juicios de tipo/intención/evidencia; OpenAI recibe texto e historial para extracción/preguntas y hechos financieros propios recuperados (productos, movimientos o solicitudes) para redactar. No se envían cookies, contraseñas ni claves de conexión. El contenido que el usuario escriba sí forma parte del contexto. Los modelos configurados son `jev-1.13.0` y `gpt-6-luna`; su disponibilidad para la cuenta y la calidad de sus respuestas requieren una prueba real posterior. Un error detiene el turno y deja una traza en logs, sin fallback silencioso.

La recuperación usa SQL fijo parametrizado, titularidad desde sesión y transacciones PostgreSQL `READ ONLY`. No hay herramientas de escritura ni modificación de roles. No se llama al adaptador de persistencia propuesto ni se crean tablas nuevas. El frontend muestra texto, sin interpretar herramientas, HTML, rutas ni código del modelo. Los formularios manuales existentes siguen separados del chat.

Conversaciones en memoria por **sesión**, con un turno simultáneo, 30 minutos de inactividad, máximo 100 sesiones con estado y 60 mensajes enviados por sesión retenida. Cada conversación admite 40 mensajes (usuario + agente). “Nueva conversación” reinicia el contexto visible; recargar no recupera el chat. Cerrar sesión elimina su estado; reiniciar API también lo pierde. El despliegue local usa un worker. No hay historial durable de estos turnos ni auditoría bancaria nueva desde el chat. Los errores tienen `traceId` y origen en logs; no se devuelven SQL, prompts internos ni el paquete privado `persistence`.

Pruebas del lector real con fixtures locales y proveedores falsos (no llamadas externas):

```sh
docker compose exec -e NEXQORI_TEST_POSTGRES=1 api python -m pytest backend/tests/test_chat_postgres.py -q -p no:cacheprovider
```

Esta prueba inicia/cierra sesiones de las dos cuentas ficticias; comprueba aislamiento, ausencia de mutaciones durante el chat y rechazo de escrituras por PostgreSQL. Las pruebas normales de API usan SQLite temporal. La prueba UI crea solicitudes ficticias manuales con marcador `UI verification`, fuera del chat.

## Recorridos disponibles

- Login y cierre de sesión, roles de servidor y preferencia ES/EN/PT persistida.
- Inicio, cuentas, tarjetas, movimientos con búsqueda/filtros y detalle por producto.
- Transferencias, pagos, préstamos, inversiones, seguros y efectivo como consultas.
- Solicitudes con confirmación, referencia, idempotencia, estado y solicitud de atención.
- Panel admin para usuarios, cola, inicio de revisión y auditoría.
- Chat: consulta el saldo propio con reglas; con Jev/OpenAI procesa tipo, intención, evidencia y RAG. Pide aclaraciones en varios turnos. Los PDF se descargan desde plantillas con datos propios; atención humana comparte contexto tras confirmación y permite mensajes con un operador. Navegación y reclamos siguen pendientes.
- Lectura de la última respuesta mediante las voces disponibles del navegador.

## Estructura y documentación

| Ruta | Contenido |
| --- | --- |
| src/ | React, rutas, componentes, tokens y diccionarios ES/EN/PT. |
| backend/ | FastAPI, permisos, modelos, fixtures, herramientas, migraciones y pruebas. |
| docker/ y compose.yaml | PostgreSQL, API y frontend con un origen local. |
| .agents/skills/nexqori-brand/ | Skill portable con identidad, idiomas, stack y reglas del agente. |
| notebooks/SERVICIOS_NEXQORI.ipynb | Análisis ejecutado con tablas, gráficos y denominadores. |
| notebooks/servicios_nexqori/ | Agregados, consultas y comprobaciones del análisis de servicios. |

Lee [arquitectura y API](docs/arquitectura.md), [chat, sesión y modelos](docs/agente.md), [servicios basados en datos](docs/servicios-basados-en-datos.md) y [guía del dataset y EDA previo](docs/dataset.md). El contrato OpenAPI está en http://localhost:5180/api/openapi.json. El [objetivo](OBJETIVO-APP.md) es contexto de producto; las capacidades futuras no están implícitamente implementadas.

## Verificación

```sh
npm test
npm run build
docker compose exec api python -m pytest backend/tests -q
npm run test:ui
```

La prueba UI requiere Docker activo con `CHAT_AGENT_MODE=rules` y Microsoft Edge; para Chromium instalado con Playwright usa `PLAYWRIGHT_CHANNEL=chromium`. Crea solicitudes ficticias con marcador `UI verification` y conserva las capturas en `.local/verification/`. Las pruebas API usan bases SQLite temporales; el recorrido UI y la persistencia se verifican en PostgreSQL de Docker. Los resultados no equivalen a una certificación bancaria.

Para desarrollo de frontend con recarga automática, usa `npm run dev` y abre http://localhost:5173 con Docker activo. Vite reenvía `/api` al origen local de Docker. Reconstruye Docker después de modificar el backend.

## Skill compartible

La skill se descubre desde `.agents/skills/nexqori-brand/`. Para usarla en otro repositorio copia esa carpeta a `.agents/skills/` e invoca `$nexqori-brand`. Incluye paleta, SVG, tokens, criterios de interfaz, tres idiomas, stack y navegación permitida. No concede permisos para operar cuentas o publicar datos.

## GitHub y datos

Repositorio privado: [nexqori/nexqori](https://github.com/nexqori/nexqori). `.gitignore` y `.dockerignore` excluyen credenciales, dataset, documentos originales, entornos, dependencias y artefactos locales. Se comparten código, documentación, skill y agregados sin identificadores. La app utiliza fixtures propios; no carga las relaciones inconsistentes del dataset en cuentas de usuario.

No se añadió una licencia pública. Compartir dentro de la organización no cambia los permisos de uso del dataset del organizador. Antes de otro entorno se necesitan servicios de identidad, TLS, copias/restauración, observabilidad, políticas operativas e integraciones verificadas.

## Documentos y atención humana

El modo `agent` ahora incorpora los códigos 6 y 7 de [chat-agente](chat-agente/README.md#pdf-y-atención-humana-en-la-aplicación). No requieren claves adicionales. Solicita un estado de cuenta informativo, un resumen de productos o un seguimiento de solicitudes; completa las aclaraciones y usa **Descargar PDF**. Marca Nexqori y textos ES/EN/PT. No se generan certificados oficiales ni saldos históricos inexistentes.

Para hablar con una persona, confirma compartir el contexto desde el chat. El administrador lo recibe en **Atención del chat**, puede revisar los mensajes y contestar; el cliente responde en la misma sección. No se escriben tablas ni se modifican permisos. Documentos: 15 minutos; atención: dos horas, logout o reinicio. Estado sólo en memoria. Los formularios bancarios manuales conservan su flujo independiente.
