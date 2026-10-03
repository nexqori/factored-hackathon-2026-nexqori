# Integración del equipo

Entrega integrada en `main` mediante [PR #3](https://github.com/nexqori/nexqori/pull/3), el 2 de octubre de 2026, America/Lima. Conserva React, FastAPI, PostgreSQL y las traducciones ES/EN/PT. La [CI final](https://github.com/nexqori/nexqori/actions/runs/37096855918) pasó: 247 pruebas API, 184 del editor, 22 frontend y 101 de Security Lab, además de las compilaciones.

| Origen | Incorporación |
| --- | --- |
| `bryan` | Banco persistente, editor de atención, contratos, reclamos, auditoría y confirmaciones. |
| Santiago: `codex/bank-intent-es-pt` (`3d85c57`) | Consultas y PDF adaptados al chat existente. Generador y plantillas con [procedencia](../backend/document_templates/provenance.json). |
| Santiago: `security-lab-module` (`b878472`) | Módulo independiente `security-lab/`, adaptado al contrato actual del banco y al puerto 5200. |
| `araceli` (`6c6766e`, autoría SofiaEscalant1) | Acceso visible a Cerrar sesión, desplazamiento del menú en ventanas bajas, manejo de errores de navegación y comprobaciones de rutas/idioma PT adaptadas al historial actual. |

La integración adapta capacidades de las ramas, no sustituye el banco por sus prototipos. El motor alternativo de chat y el panel de atención en memoria se reemplazan por las conversaciones, reclamos y panel administrativo persistentes ya disponibles. Los notebooks y documentos privados no se publican. Los subagentes usados durante el trabajo pertenecen a Codex, no al aplicativo.

`araceli` partía de la base inicial y llevaba los reclamos a Mis solicitudes. Aquí se conserva la separación actual: el flujo conectado continúa en el chat y un reclamo confirmado va a Mis reclamos. Las rutas proceden del comando validado, no de un segundo mapeo de intención que lo sustituya. Se conserva el HTML de EDA vigente; la regeneración incluida en esa rama no cambia estos recorridos.

## Revisión funcional de ramas — 3 de octubre de 2026

Se compararon los commits de la tabla con el código integrado, además de verificar su ascendencia. Catálogo (`30df4b4`), laboratorio (`dd053f1`) y Araceli (`6c6766e`) están incorporados al historial. Las capacidades de Santiago y Security Lab se adaptaron; sus puntas originales no son antecesores del banco. No se encontró una omisión que impida las pruebas acordadas, pero **no hay paridad completa con el prototipo de chat humano**.

| Capacidad de las ramas | Resultado y evidencia |
| --- | --- |
| Consulta/problema, aclaraciones y memoria | Adaptadas al flujo compartido, [contexto seguro](contexto-conversacion.md) y PostgreSQL. [LangGraph](langgraph-atencion.md) planifica los bloques. |
| Saldos, movimientos, tarjetas y seguimiento | Lecturas propias en [herramientas](../backend/agent_tools.py) y [respuestas](../backend/query_answers.py). No se importó el RAG que enviaba registros bancarios al modelo. |
| Tres PDF, plantillas ES/EN/PT y descarga | Incorporados con [procedencia](../backend/document_templates/provenance.json). El [formulario de parámetros](consultas-y-documentos.md) sustituye la extracción automática desde lenguaje natural. Documentos persistentes del titular sustituyen el almacenamiento temporal de 15 minutos del prototipo. |
| Derivación, trazabilidad y revisión administrativa | Disponibles en [reclamos](panel-reclamos.md), con confirmación y auditoría. |
| Chat bidireccional cliente–operador | **No incorporado:** tampoco asignación automática ni consulta periódica de mensajes del operador. El prototipo usaba `chat_actions.py` y rutas `chat-handoffs` con almacén en memoria. La derivación actual no conecta con un operador ni equivale a ese chat. Implementarlo requeriría un flujo persistente propio. |
| Security Lab | Catálogo, ejecuciones, revisión, hallazgos, retest, exportaciones y roles incorporados en [su módulo](../security-lab/README.md). No se eliminaron archivos del módulo original; puertos, sondas y aislamiento se adaptaron al banco. Las pruebas bloqueadas siguen identificadas como bloqueadas. |
| Navegación y Cerrar sesión de Araceli | Incorporados y probados; comando validado y logout visible. Se omitieron el segundo mapa de rutas obsoleto y el EDA regenerado, conforme al alcance indicado. |
| Voz | Aplazada. La rama original tampoco contiene un motor de llamada/transcripción que pueda activarse mediante este merge. |

Esta revisión documenta diferencias; no convierte las capacidades omitidas en un nuevo backlog. La propuesta de especialista del editor continúa mostrando qué se activaría.

## Qué probar

1. Actualiza `main`, instala dependencias y reconstruye Docker como indica [INICIO-EQUIPO](../INICIO-EQUIPO.md). Las migraciones conservan registros; no borres el volumen.
2. En [Servicios](http://localhost:5180/services), consulta un recibo por número o código y confirma el pago. Comprueba el movimiento y su comprobante. Prueba otra referencia y un pago parcial permitido. [Guía](pagos-y-transferencias.md).
3. Transfiere a la referencia de otro cliente Nexqori. Revisa el débito y, entrando como destinatario, el crédito. No hay transferencia a una red externa.
4. Consulta saldo o movimientos en el chat. Continúa el mismo tema y pide un PDF. Elige parámetros; al generarlo se abre [Mis solicitudes](http://localhost:5180/requests), con descarga y detalle. El archivo también permanece en la conversación.
5. Reporta un problema y responde las preguntas pendientes. El contrato se conserva mientras se completa el contexto. Registrar el reclamo exige confirmación; su evolución aparece en Mis reclamos.
6. Para repetir la aceptación con usuarios nuevos, ejecuta `npm run test:banking`. Guarda los accesos y evidencias sólo en `.local/verification/banking-integrated/`. El script valida datos, reintentos, UI e idiomas; no consume modelos. Las pruebas de navegador que cambian perfiles deben correr en serie.

## Tres interfaces locales

| Puerto | Aplicación | Arranque |
| --- | --- | --- |
| 5180 | Banco | `npm run docker:up` en la raíz. |
| 5190 | Editor de atención y evaluaciones de intención | [Guía del editor](../experiments/intent-lab/README.md). Configuración y claves permanecen en `.local/intent-lab/`. |
| 5200 | Security Lab | `cd security-lab`, `npm ci`, `npm run setup`, `docker compose up --build -d`; [alta local de administrador](../security-lab/README.md). |

Security Lab tiene otra base de datos y un objetivo aislado: una copia del banco sin proveedores externos. Sus pruebas no se ejecutan contra las cuentas del banco principal. El catálogo distingue pruebas automatizadas, manuales, no aplicables y resultados sintéticos; no presenta los sintéticos como mediciones reales ni acredita seguridad bancaria completa. El editor de atención conserva su puerto y sus resultados.

## Límites conservados

Los registros de evaluación son ficticios y persistentes. Las facturas no prueban convenios con proveedores. Las transferencias producen dos asientos locales, sin liquidación externa. Los PDF son informativos y conservan la instantánea solicitada. Las devoluciones exigen aprobación administrativa. La voz sigue aplazada. Las claves, respaldos, transcripciones y documentos originales no forman parte de Git.
