# Fuentes y decisiones de cobertura

Consulta: 2026-10-02, America/Lima. Versión del catálogo: 1.0.0.

La [referencia solicitada](https://cybersecurityswitzerland.com/encyclopedia/llm-security-testing/) sirve de índice de métodos. No se incorporan sus estadísticas generales como evidencia de Nexqori ni sus ejemplos de CLI como comandos vigentes. Cada método de sus diez secciones se identifica en `lab/catalog.py`; hay 56 filas de fuente y diez escenarios propios. Las variantes internas de extracción/codificación figuran en procedimientos. El catálogo y las ejecuciones exportan la matriz trazable, incluidos IDs de resultados y revisiones.

## Contraste primario

- [OWASP GenAI](https://genai.owasp.org/llm-top-10/): la página consultada publica los diez riesgos 2025. Se conserva explícitamente `LLMxx:2025`; no se mezcla con 2023–24 ni se presume una versión posterior.
- [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework): marco de gestión, no scanner ni certificación. Gobernar: roles, permisos y auditoría; mapear: inventario y alcance; medir: escenarios y métricas; gestionar: hallazgos, corrección y retest. El enlace por caso es una correspondencia de diseño del laboratorio, no una validación NIST.
- [MITRE ATLAS](https://atlas.mitre.org/): el sitio no permitió verificar de manera fiable el catálogo de técnicas mediante la lectura disponible. Los IDs quedan `pending_verification` y null. No se copia como confirmado el identificador del ejemplo de la fuente secundaria.

## Herramientas consideradas

| Herramienta / documentación primaria | Decisión local |
|---|---|
| [Garak](https://github.com/NVIDIA/garak) | Candidato para sondas de un modelo autorizado. No integrado: objetivo rules y sin llamadas externas. |
| [PyRIT](https://github.com/Azure/PyRIT) | Candidato para escenarios conversacionales; requiere adaptador y evaluación propia. No integrado. |
| [ART](https://github.com/Trusted-AI/adversarial-robustness-toolbox) | Orientado a componentes ML disponibles para evaluación; sin pesos o entrenamiento local aplicable. |
| [Counterfit](https://github.com/Azure/counterfit) | No se añade otra capa de ejecución; no hay adaptador evaluado para este objetivo. |
| [ModelScan](https://github.com/protectai/modelscan) | Sería útil para artefactos de modelos serializados; no se cargan tales artefactos. |
| [TextAttack](https://github.com/QData/TextAttack) | Posible generación de variantes lingüísticas futura; sin instalación ni evaluación aquí. |
| [Rebuff](https://github.com/protectai/rebuff), [LLM Guard](https://github.com/protectai/llm-guard), [Vigil](https://github.com/deadbits/vigil-llm) | Son posibles controles de detección; instalar un detector no demuestra seguridad ni autoriza enviar prompts. No incorporados. |
| HiddenLayer, Lakera Guard, Robust Intelligence, CalypsoAI | Menciones comerciales de la fuente, sin integración, credenciales ni evaluación de producto en esta entrega. |

Burp, SQLMap, k6, Locust, RAGAS, Dependency-Check y Snyk también aparecen como apoyos en la fuente. No se invocan comandos de estas herramientas. Las pruebas locales usan HTTPX fijado y funciones registradas, revisión de código y evidencia manual. El análisis de avisos de dependencias requiere una base de avisos fechada; un lock fijado no prueba ausencia de vulnerabilidades.

## Aplicabilidad real

El repositorio principal sí contiene integración Jev/OpenAI y RAG mediante SQL de sólo lectura. Las guías antiguas no representan íntegramente su estado vigente. El laboratorio deliberadamente crea un objetivo rules separado y sin claves: los métodos semánticos quedan bloqueados, no «aprobados por simulación». No existe almacén vectorial ni entrenamiento operativo en el objetivo.

Las pruebas de SQL/XSS/comandos/código con dobles se ofrecen como revisión manual guiada con referencias a los consumidores y evidencias exigidas. No se promete que una revisión manual equivalga a una explotación automatizada. La concurrencia automatizada es únicamente una sonda de dos lecturas; pruebas de carga requieren un alcance adicional.

## Cadencia sugerida, sin automatizaciones activadas

Revisar permisos y aislamiento al cambiar endpoints; confirmación/idempotencia al cambiar escrituras; salida y citas al cambiar prompts o modelos; procedencia y controles de acceso al cambiar datos; límites al cambiar herramientas. Repetir la suite local antes de integrar cambios. La periodicidad organizacional, evaluaciones regulatorias y pruebas externas requieren planificación específica; no hay calendario ni mensajes automáticos.
