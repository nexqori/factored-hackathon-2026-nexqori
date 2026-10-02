# Empezar con Nexqori

Panel de evaluación: [editor de flujos e incidencias](docs/editor-flujos-lab.md). En `http://localhost:5190/?view=flows&mode=editor&lang=es` puedes crear y conectar bloques, configurar contexto ES/EN/PT y ejecutar el grafo guardado. La plantilla Incidencia de la app genera logs y avisos locales sin modelos. `npm run test:lab:editor` verifica ese recorrido; `npm run test:lab:flows` conserva el [visor anterior](docs/lab-flujos-react-flow.md). Voz aplazada.

Pruebas repetibles: [tres casos con acciones y auditoría](docs/pruebas-tres-casos.md). `npm run test:cases` ejecuta bloqueo, devolución y derivación ES/EN/PT. `npm run test:cases:prepare` crea accesos privados nuevos para practicarlos manualmente.

Recorridos nuevos: [segunda atención en el LAB](docs/evaluacion-segunda-atencion.md) y [aprobación, ID de operación y consulta del movimiento](docs/trazabilidad-solicitudes.md). Mis solicitudes distingue aprobación pendiente, abono y rechazo; en Movimientos puedes iniciar un chat contextual. Jev y Luna se mantienen en el LAB.

Esta es la base de trabajo del equipo: React + TypeScript, FastAPI y PostgreSQL, en Docker local, con identidad Terracota suave y español, inglés y portugués. El repositorio es privado: [nexqori/nexqori](https://github.com/nexqori/nexqori).

## Arranque

Requisitos: acceso al repositorio, Git, Node.js 24 y Docker Desktop iniciado con contenedores Linux. Clona el proyecto y usa la rama del PR hasta que se integre en `main`.

```sh
git clone https://github.com/nexqori/nexqori.git
cd nexqori
git switch bryan
npm ci
npm run setup
npm run docker:up
```

Abre [Nexqori local](http://localhost:5180). Para comprobar los servicios:

```sh
docker compose ps
docker compose logs --tail=60 api
```

La primera ejecución aplica las migraciones y crea las cuentas iniciales. El setup genera claves propias de cada integrante en `.env`; no las compartas ni las subas a Git. El dataset original no se necesita para iniciar la aplicación.

| Perfil | Correo o documento | Contraseña en `.env` |
| --- | --- | --- |
| Cliente Andrea | `andrea@nexqori.com` o `00000001` | `CUSTOMER_PASSWORD` |
| Administradora Nora | `admin@nexqori.com` o `00000002` | `ADMIN_PASSWORD` |
| Segundo cliente Mateo | `mateo@nexqori.com` o `00000003` | `SECOND_CUSTOMER_PASSWORD` |

Las direcciones y documentos identifican cuentas locales; no verifican buzones ni documentos oficiales. Las contraseñas persistidas no cambian al editar `.env` después del primer arranque.

## Primer recorrido

1. Entra como Andrea. Revisa cuentas, tarjetas y movimientos.
2. Abre **Servicios** y busca **pagar celular**. Aparece **Empresa Telefónica**. También se puede buscar Internet Plus, Cable TV, servicios públicos o una gestión como transferencia, préstamo o cargo no reconocido.
3. Elige una cuenta propia, escribe la referencia e importe, revisa y confirma la solicitud. Conserva la referencia y abre **Mis solicitudes** para ver empresa, datos y seguimiento. Este flujo registra una solicitud; no debita saldos ni paga al proveedor.
4. Pide al asistente **quiero pagar celular**. Abre el mismo formulario. **Nueva** inicia una conversación vacía; **Conversaciones** recupera una anterior.
5. Cambia entre Español, English y Português. En **Configuración**, prueba letra pequeña, mediana y grande. El perfil conserva esas preferencias.
6. Entra como Nora y abre la solicitud para revisar su detalle e iniciar revisión. Mateo permite comprobar el aislamiento: no ve productos, conversaciones ni solicitudes de Andrea.

## Dónde comenzar a desarrollar

Antes de editar, lee [ESTADO.md](ESTADO.md) y [AGENTS.md](AGENTS.md). Mantén un solo estado por proyecto y registra únicamente el frente que trabajes. Crea una rama para tus cambios.

| Trabajo | Entrada al código |
| --- | --- |
| Pantallas, rutas y shell | [src/App.tsx](src/App.tsx) |
| Búsqueda y formularios de servicios | [src/Services.tsx](src/Services.tsx), [src/services.css](src/services.css) |
| Definiciones y sinónimos de servicios | [backend/service_catalog.json](backend/service_catalog.json), [backend/catalog.py](backend/catalog.py) |
| API, validaciones y permisos | [backend/main.py](backend/main.py), [backend/schemas.py](backend/schemas.py), [backend/security.py](backend/security.py) |
| Modelo y cambios de base | [backend/models.py](backend/models.py), [backend/migrations/versions/](backend/migrations/versions/) |
| Asistente y destinos permitidos | [src/AssistantPanel.tsx](src/AssistantPanel.tsx), [backend/assistant.py](backend/assistant.py), [backend/navigation.py](backend/navigation.py), [src/navigation.ts](src/navigation.ts) |
| Idiomas, configuración y marca | [src/locales/](src/locales/), [src/Settings.tsx](src/Settings.tsx), [skill Nexqori](.agents/skills/nexqori-brand/SKILL.md) |
| Orquestación local | [compose.yaml](compose.yaml), [docker/](docker/) |

Para añadir un servicio, conserva un ID estable, tipo de recorrido, categoría, textos y sinónimos ES/EN/PT. Documenta su fuente antes de añadir nombres de empresas. Las reglas bancarias nuevas van en servidor; las propuestas del asistente no autorizan operaciones. Si cambias persistencia, añade una migración que conserve datos. La guía [catálogo y evidencia](docs/catalogo-servicios.md) explica qué viene del dataset y qué es diseño de la app.

Para trabajar con recarga de frontend:

```sh
npm run dev
```

Abre [Vite](http://localhost:5173) con Docker activo: `/api` se reenvía al backend local. Después de cambiar backend o para actualizar la vista en el puerto 5180, ejecuta `npm run docker:up`.

## Comprobaciones antes del PR

```sh
npm test
npm run build
docker compose exec api python -m pytest backend/tests -q
npm run test:ui
npm run test:experience
npm run test:services
```

Las pruebas de navegador usan Microsoft Edge instalado. Para Chromium de Playwright, instala su navegador con `npx playwright install chromium` y define `PLAYWRIGHT_CHANNEL=chromium` en tu terminal. Los recorridos integrales crean solicitudes identificadas como verificación y guardan capturas locales en `.local/verification/`. CI ejecuta pruebas de frontend, compilación y pruebas API; los recorridos Docker/navegador se ejecutan localmente.

Para detener la base conservando datos:

```sh
npm run docker:down
```

No borres el volumen PostgreSQL para actualizar la aplicación. Las migraciones de conversaciones y solicitudes no tienen una reversión destructiva automática: una reversión de esquema requiere restaurar un respaldo verificado.

## Alcance de esta entrega

Hay autenticación local, permisos, persistencia PostgreSQL, catálogo de 20 servicios, solicitudes con confirmación/idempotencia/auditoría, administración, conversaciones, perfiles, preferencias, bloqueo de tarjetas y devoluciones con revisión. Los cuatro nombres de empresas provienen de agregados del dataset; eso no acredita convenios de recaudación.

Las devoluciones aprobadas por un administrador abonan el saldo local. No hay liquidación externa, libro mayor de doble partida, proveedor de pagos ni LLM en el chat bancario. Jev/Luna funcionan por separado en el LAB. La **voz corresponde a otra implementación** y esta base no instala motores de audio. MFA, recuperación de cuentas e integración bancaria requieren un alcance posterior explícito. Los límites se explican en documentación; las pantallas conservan el tono natural acordado.

Lecturas: [arquitectura y API](docs/arquitectura.md), [catálogo y evidencia](docs/catalogo-servicios.md), [acceso y conversaciones](docs/acceso-y-conversaciones.md), [contrato del agente](docs/agente.md), [README](README.md). OpenAPI: [contrato local](http://localhost:5180/api/openapi.json).

## Pruebas en la rama bryan

`git switch bryan` y `docker compose up --build -d` aplican también la migración de metadatos de tarjetas sin reemplazar registros. Abre [Tarjetas](http://localhost:5180/cards). La consulta completa pide la contraseña y se oculta automáticamente. Ejecuta `npm run test:cards`; las pruebas de navegador deben correr en serie porque comparten perfiles locales.

Consulta [tarjetas y mapeo del dataset](docs/tarjetas-y-dataset.md), [procedimientos y contratos](docs/contratos-atencion.md) y [LAB independiente](experiments/intent-lab/README.md). El proveedor de tarjetas es local y no autoriza compras; PostgreSQL no contiene una importación del dataset. Luna high está conectado y probado con los cinco casos del LAB; las acciones del banco permanecen separadas. Consulta [registro, auditoría, texto pegado y conversación por contratos](docs/registro-auditoria-y-conversacion.md).

El LAB incorpora **Ruta y herramientas**: Jev deriva cada turno a consulta, queja/problema, servicio o aclaración. El servidor fija las lecturas y acciones revisables. La [guía de enrutamiento](docs/enrutamiento-jev-herramientas.md) incluye mapa completo, API de lectura propia y pasos para probar; ninguna herramienta se ejecuta desde el LAB.

El login incluye Crear mi perfil. Configuración permite cambiar experiencia y acompañamiento. Administración muestra la auditoría filtrable y acceso registrado a conversaciones. Iniciar llamada abre sólo la presentación visual, sin micrófono ni backend de voz.

## Bloqueos y devoluciones

En [Tarjetas](http://localhost:5180/cards), el titular puede bloquear su tarjeta con contraseña y confirmación. En **Mis solicitudes**, un reclamo de cargo completado permite pedir devolución; el administrador abre el mismo folio, revisa la evidencia y aprueba o rechaza. Sólo la aprobación abona la cuenta del titular y crea un movimiento. No se puede elegir importe o cuenta ajena.

El LAB activa contratos sólo para problemas; consultas y servicios siguen recorridos separados. Sus enlaces abren el banco autenticado y nunca ejecutan operaciones por sí mismos. [Guía de acciones, reglas, endpoints y pruebas](docs/acciones-problemas.md). Actualiza Docker sin borrar volúmenes; la migración `a318d902bc44` conserva los registros existentes.
