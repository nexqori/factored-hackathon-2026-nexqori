# Nexqori

Antes de trabajar, lee `ESTADO.md` en la raíz principal indicada por `git worktree list --porcelain`. Mantén un único estado por proyecto; relee antes de actualizar sólo el frente trabajado, preservando los demás. Registra fecha America/Lima, tareas concretas [ ]/[x], evidencia, bloqueos y siguiente paso. Distingue implementado, desplegado y validado. Los antecedentes no son un backlog autorizado.

Para diseño, idioma o navegación usa [.agents/skills/nexqori-brand/SKILL.md](.agents/skills/nexqori-brand/SKILL.md). Conserva la paleta elegida y las traducciones ES/EN/PT con igual cobertura.

Stack acordado: React + TypeScript, FastAPI y PostgreSQL, con Docker Compose local. La interfaz está en `src/`, la API y los fixtures coherentes en `backend/`. Lee `docs/arquitectura.md`, `docs/agente.md` y `docs/servicios-basados-en-datos.md` según el cambio. Mantén autorización en servidor, aislamiento por usuario, confirmación, idempotencia y auditoría. localStorage sólo guarda la preferencia de idioma. Los documentos originales, datos, entornos y credenciales permanecen locales.

Comprobaciones: `npm test`, `npm run build`, `python -m pytest backend/tests -q` en el entorno del backend; para cambios de recorridos o presentación, `npm run test:ui` con Docker iniciado en localhost:5180. La prueba visual usa registros ficticios persistentes, identificados como verificación. No publicar datos, credenciales ni PDFs del organizador. Mantén explícitos los límites de la demo y usa sólo destinos permitidos para el agente; sus mensajes nunca son autorización para ejecutar operaciones.
