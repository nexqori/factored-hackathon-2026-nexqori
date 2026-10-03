# Nexqori Security Lab

Aplicación independiente para evaluar contratos de seguridad de una copia local de Nexqori, conservar evidencia y gestionar revisiones. React + TypeScript, FastAPI, PostgreSQL y worker con cola persistente. Interfaz ES/EN/PT, identidad Terracota suave.

## Inicio local

Desde la raíz del repositorio, con Docker Desktop y Node disponibles:

```powershell
cd security-lab
npm run setup
docker compose up --build -d
docker compose exec lab-api python -m lab.cli create-admin administrador
```

La última orden pide la contraseña de forma oculta dos veces, con un mínimo de 14 caracteres. No hay contraseña predeterminada ni usuario de producto creado automáticamente. Después abre **http://localhost:5190**. El setup genera únicamente secretos de servicios en `security-lab/.env`, excluido de Git; nunca lee `.env` raíz. No compartas ese archivo.

La aplicación principal conserva `http://localhost:5180`. El laboratorio usa el nombre Compose `nexqori-security-lab`; no añadas `-p nexqori` ni reutilices sus volúmenes. El objetivo está sólo en una red Docker interna: no hay URL pública ni navegador del objetivo en 5191.

```powershell
# Apagar sin borrar evidencias ni fixtures:
docker compose down
# Encender nuevamente:
docker compose up -d
# Cambiar una contraseña y revocar sesiones de esa cuenta:
docker compose exec lab-api python -m lab.cli reset-password administrador
# Ver estado sin imprimir configuración ni secretos:
docker compose ps
```

No uses `down -v` si necesitas conservar evaluaciones. Los volúmenes `lab_data` y `target_data` contienen respectivamente evidencia y fixtures sintéticos persistentes. Restaurar una copia es una operación local revisada; no hay borrado automático. Para backup, utiliza `pg_dump` dentro de `lab-db` y conserva el archivo fuera de Git; verifica una restauración en un proyecto Compose separado antes de confiar en ella.

## Recorrido

1. En Administración crea operadores/lectores y habilita o deshabilita destinos. Las cuentas comparten el espacio autorizado del equipo; lector no puede ejecutar, revisar ni administrar.
2. En Catálogo consulta los pasos, prerrequisitos y criterio. Selecciona casos, destino, idioma y límites. Revisa el alcance y confirma explícitamente.
3. En Evaluaciones observa progreso, cancela si es necesario y abre evidencia por caso. Se conserva el estado operativo separado del veredicto.
4. Para un caso manual terminado, registra criterio concreto, evidencia sintética, impacto y recomendación. Puedes cargar TXT/JSON UTF-8 de hasta 16 KB. El archivo se transforma en texto y no se ejecuta.
5. En Hallazgos asigna responsable y marca una corrección. Vuelve a la evaluación original y prepara un retest. Sólo un resultado aprobado en retest enlazado verifica la corrección.
6. Compara ejecuciones compatibles y exporta JSON, CSV o HTML imprimible. La revisión original nunca se sobrescribe.

Separa `HTTP real · rules` de `DEMO · simulación determinista`. La demostración genera una falla deliberada de alcance para ejercitar hallazgos, sin tráfico al objetivo. Ningún resultado simulado prueba resistencia de un LLM.

## Cobertura

El catálogo v1 contiene 66 casos: 56 métodos de las diez secciones de la fuente y diez contratos adicionales de Nexqori. Estado inicial: **13 automatizados, 13 manuales, 31 bloqueados, nueve no aplicables**.

Automatización real: aislamiento de recursos, errores HTTP, consentimiento, destinos/identidad/rol inyectados, dos lecturas concurrentes, acceso anónimo y rol, CSRF/origen, idempotencia, operación ajena, revocación, tamaño de entrada, controles benignos ES/EN/PT y ausencia de efectos autorizados por mensajes.

El objetivo usa el mismo código actual de Nexqori, pero un seed/base propios y `rules` obligatorio. Los métodos semánticos están bloqueados por ausencia de un modelo autorizado en **este objetivo**, aunque el aplicativo principal sí tenga integración Jev/OpenAI. No se incorporan claves, proveedores, embeddings ni entrenamiento. El laboratorio no cambia el fallback ni los contratos principales.

Los documentos PDF y la atención humana dependen del modo agent para producir artefactos; su aislamiento dinámico queda sujeto a ese prerrequisito. Las comprobaciones de vectores no se atribuyen a la recuperación SQL. La sonda concurrente no es una prueba de carga. El dashboard no asigna puntuación global ni afirma certificación.

- [Arquitectura y modelo de amenazas](docs/architecture.md)
- [Fórmulas, denominadores y revisión](docs/metrics.md)
- [Fuentes, herramientas y aplicabilidad](docs/sources.md)
- [Matriz fuente → caso → método](docs/coverage.md)

## Pruebas

En `security-lab/`:

```powershell
npm ci
npm test
npm run build
docker compose exec lab-api python -m pytest tests -q -p no:cacheprovider --basetemp=/tmp/lab-pytest
npm run test:ui
```

El smoke requiere Edge instalado (`PLAYWRIGHT_CHANNEL` permite otro canal existente). Crea un administrador temporal aleatorio, lo desactiva y revoca sus sesiones al finalizar. No escribe su contraseña en archivos ni salida. Las evaluaciones, revisiones DEMO y registros `Security Lab verification` permanecen como evidencia. Capturas y reportes están en `.local/verification/`, excluido de Git. Comprueba HTTP real, DEMO, ciclo de hallazgo/retest, exportación, persistencia tras reinicio, idiomas, móvil, accesibilidad automatizada y contenido hostil inerte.

Para pytest sin Docker, usar un entorno con `requirements.lock`, `PYTHONPATH` apuntando a `security-lab` y un directorio temporal local preparado. Las pruebas unitarias usan SQLite temporal; el smoke verifica PostgreSQL real. Una prueba unitaria aprobada no equivale a validación de PostgreSQL.

Después de cambios conserva también las comprobaciones principales: `npm test`, `npm run build`, `python -m pytest backend/tests -q` y `npm run test:ui` desde la raíz. El último necesita 5180 y modo rules durante su ejecución para no llamar proveedores. El script `scripts/main-regression.ps1` crea un override temporal, restaura la configuración Compose raíz en `finally` y no modifica `.env`.

## Cambios y extensiones

`lab/catalog.py` es el contrato versionado. `lab/adapters.py` contiene sólo ejecutores registrados. Añadir un destino externo requiere revisión de red, autorización de datos y un nuevo adaptador: no se puede introducir desde el panel. `npm run setup` registra hashes de fuentes antes de cada reconstrucción. Cada ejecución guarda además el catálogo completo de ese momento para preservar denominadores y referencias tras cambios.

Las migraciones Alembic se aplican al arrancar API antes de worker. No se ejecutan migraciones del laboratorio en la base principal. La versión inicial describe el esquema actual; cambios posteriores requieren una revisión Alembic nueva y pruebas de actualización.

La auditoría es local y persistente, no inmutable. Mantén un solo worker/API. El despliegue actual no cubre TLS público, MFA, alta disponibilidad o aislamiento multiempresa. No se han activado tareas periódicas, proveedores externos ni publicación.
