# Arquitectura y amenazas

Fecha: 2026-10-02, America/Lima. Alcance: laboratorio local de un equipo de desarrollo.

El Compose `nexqori-security-lab` tiene seis servicios y dos bases PostgreSQL. Web publica únicamente `127.0.0.1:5190`; API y bases no publican puertos. La red `lab` conecta web/API/worker/base del laboratorio. La red `target` conecta worker/objetivo/base del objetivo. Ambas son internas. Sólo web tiene red de entrada. Ningún servicio monta código del host ni el socket Docker.

El objetivo se construye con el backend vigente del repositorio y sus fixtures coherentes. No monta datos del organizador, `.env` raíz, PDF ni claves externas. Fuerza `CHAT_AGENT_MODE=rules`, `INTENT_MODE=off` y envío externo deshabilitado. El objetivo conserva endpoints actuales aunque las funciones semánticas dependan de proveedores ausentes. `http://localhost:5191` es sólo el origen HTTP lógico aceptado por el adaptador; no hay servicio publicado en ese puerto.

## Confianza y permisos

- Navegador → API: cookies opacas, hash de sesión en PostgreSQL, expiración fija de ocho horas, HttpOnly, SameSite Strict, origen y CSRF en mutaciones. El HTTP local no usa Secure; para un futuro TLS debe activarse `LAB_COOKIE_SECURE=true` y ajustar orígenes explícitos.
- Los usuarios del laboratorio pertenecen al mismo equipo. Todos los lectores autorizados pueden consultar sus evaluaciones y evidencias. Operadores ejecutan y revisan; administradores gestionan miembros, destinos y auditoría. No es una plataforma multiempresa ni implica aislamiento de resultados entre operadores del mismo equipo.
- Las identidades y cookies del objetivo son distintas. Cambiar permisos o desactivar una cuenta revoca sus sesiones. No hay registro público ni contraseña inicial fija. La CLI usa getpass y no acepta contraseñas en argumentos.
- El catálogo, los adaptadores y destinos son código versionado. El administrador puede habilitar/deshabilitar los dos destinos predefinidos; no añadir una URL. No hay ejecución de shell desde la UI.
- Las evidencias son texto, incluso cuando contienen HTML o instrucciones. Las cargas TXT/JSON se convierten a texto UTF-8, con límite; el servidor limita cuerpo y campos independientemente del navegador. La redacción es defensa adicional, no garantía de detectar todo secreto: sólo debe cargarse evidencia sintética revisada.

## Ejecución y recuperación

Una tabla PostgreSQL mantiene la cola. Un worker obtiene un advisory lock de por vida; un segundo worker no puede ejecutar. Cada caso automatizado vive en un proceso hijo terminado al cancelar o vencer el plazo. El transporte usa destino constante, ignora proxies, rechaza redirecciones, limita respuesta a 256 KiB y cada petición a dos segundos. Concurrencia del worker: un caso; la sonda de concurrencia hace sólo dos lecturas.

Límites de UI/backend: 10 evaluaciones pendientes/activas, 30 peticiones por caso, 30 segundos por caso y 600 segundos por evaluación como máximos. Valores iniciales 30/20/300. El catálogo guarda el alcance de cada ejecutor. No se construye un generador arbitrario de tráfico.

Al reiniciar el worker se marcan ejecuciones en marcha como error/inconclusas; jamás se repiten automáticamente. Las pendientes siguen en cola. Las operaciones ya enviadas al objetivo pueden haber terminado antes de una cancelación: sus efectos sintéticos permanecen identificados como `Security Lab verification`. Los hijos no heredan claves del aplicativo principal. Las sesiones del objetivo se cierran al finalizar normalmente; tras terminación forzada caducan por el mecanismo del objetivo.

## Amenazas y controles

| Amenaza | Control | Comprobación |
|---|---|---|
| Usar panel sin sesión o elevar rol | Dependencias FastAPI en cada recurso | pytest anónimo/lector/operador |
| CSRF y robo por JavaScript | Origin + CSRF + HttpOnly | pytest y navegador |
| Acceso al aplicativo principal o SSRF | Adaptador fijo + red interna sin ruta al principal | validación API, Compose, tests |
| Inyección de comandos | Ninguna ruta de ejecución libre | revisión de adaptadores |
| Payload activo en reporte | React escapa; HTML usa html.escape y CSP; CSV neutralizado | prueba de evidencia hostil |
| Evidencia falsa o juicio no sustentado | Original inmutable, revisiones con actor/criterio/impacto | pruebas de revisión/retest |
| Agotamiento por pruebas | Cuotas, plazo y procesos cancelables | pruebas de timeout/cancelación |
| Duplicación tras reinicio | Estado durable, no replay de running | recuperación y reinicio real |
| Filtrar datos del organizador | Fixtures nuevos del seed existente, sin montajes reales | inspección de Compose/contexto |

## Límites operativos

Un proceso API y un worker, sin alta disponibilidad; no escalar réplicas sin revisar bloqueo, límites y semántica de recuperación. La auditoría es persistente y no tiene API de edición, pero un administrador de PostgreSQL puede alterarla. No es inmutable ni certificada. La cuenta PostgreSQL inicial administra su base local; no debe reutilizarse en producción. Sin MFA, TLS público, gestor de secretos externo ni backup automático. Los reportes descargados quedan bajo responsabilidad del operador.

PostgreSQL del laboratorio y del objetivo están separados por contenedor, rol, contraseña, volumen y red. Los hashes de fuentes se registran al ejecutar setup, incluyendo cambios sin commit. No se afirma reproducibilidad bit a bit de respuestas LLM: no se llama ningún LLM.
