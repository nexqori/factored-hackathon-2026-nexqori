# Evaluación de intención antes de activar un modelo

Estado: protocolo preparado, sin evaluación semántica de modelos reales ni mejora demostrada. La integración de chat-agente tiene pruebas técnicas con proveedores falsos y PostgreSQL; estas pruebas no miden precisión, calibración ni disponibilidad de APIs. La clasificación es un componente del recorrido bancario; no acredita resolución de casos.

## Datos y etiquetas

El EDA previo en ESTADO.md documenta 171.321 transcripciones sobre saldo, 42 variantes y categorías incompatibles con el contenido; los reclamos usan descripciones genéricas. No reetiquetar por category/reason_category/detected_intents sin revisión textual. Las cifras proceden del análisis previo, no de una nueva ejecución. Los volúmenes de los PDF son descriptivos, no sustituyen el inventario local medido.

Preparar un manifiesto local con fuente, ID seudónimo, versión/hash, campo de texto, idioma, fecha disponible, transformación, calidad, grupo de duplicados, etiqueta revisada, revisor y partición. No incluir datos originales en artefactos públicos. Mantener snapshots originales intactos; detectar nulos, cambios de esquema, llegadas tardías y relaciones inconsistentes. Versionar cada lote; una llegada tardía se incorpora a un nuevo manifiesto sin contaminar el test congelado. No interpretar process_date como disponibilidad temporal sin comprobarlo.

Separar ejemplos originales, derivados, traducidos y creados por el equipo. Revisar ES y PT y mantener regresión EN. Las traducciones requieren revisión, no prueban cobertura real del corpus en portugués. No inferir intención por nacionalidad o acento.

Agrupar duplicados exactos, variantes de plantilla, traducciones y turnos de una conversación antes de dividir desarrollo/validación/test. Mantener cada grupo en una sola partición. Congelar test antes de ajustar preguntas o umbrales. Si hay pocos grupos/clases, declarar evaluación insuficiente en vez de reportar generalización. Los ejemplos de la taxonomía son desarrollo, nunca test reservado.

## Comparación

Comparar classify/answer actuales con cada candidato sobre el mismo conjunto reservado y contexto permitido. Registrar commit del baseline, versiones de modelo, taxonomía, política y preguntas. Ajustar umbrales y calibración sólo con validación; reportar también variación entre ejecuciones cuando corresponda.

Medir precisión/recall/F1 por intención, macro-F1 y matriz de confusión, por idioma y con denominadores. Medir cobertura de aceptación, error entre aceptadas, abstención y aclaración. Para probabilidades, usar Brier/log-loss y curvas de calibración; no asignar porcentajes a reglas. Reportar p50/p95, errores, timeouts, reintentos y coste por intento. No comparar escalas de proveedores sin validación.

Incluir solicitudes normales, negación, varias intenciones, desconocidas, seguimiento contextual, atención humana, inyección de instrucciones, datos faltantes, salida malformada, proveedor caído, sesiones expiradas y acceso ajeno. Evaluar el recorrido completo por separado: confirmación, aislamiento, idempotencia, acciones verificadas y calidad del contexto de derivación. Distinguir atención simulada de operador conectado; no afirmar movimientos monetarios.

## Puertas de activación

- Mantener off mientras no haya adaptador probado, etiquetas revisadas y modelo fijado.
- Elegir y documentar criterios numéricos de aceptación antes de abrir test; los umbrales null de la política bloquean active.
- Exigir mejora o tradeoff justificado respecto al baseline, con muestras suficientes por clase/idioma y fallos incluidos.
- Conservar cero regresiones observadas de autorización, confirmación y navegación en las pruebas; esto no demuestra riesgo cero.
- Ejecutar npm test, npm run build y pytest del backend. Si se modifica presentación o recorridos, ejecutar npm run test:ui con Docker en localhost:5180.
- Shadow debe preservar respuestas y escrituras actuales; proveedor no disponible debe conservar el flujo guiado. Validar reversión a off sin perder datos.

Guardar corpus, etiquetas, particiones y resultados en `.local/intent-evaluation/`. Publicar únicamente agregados revisados sin textos ni identificadores del dataset. Documentar límites, muestras y fallos; no presentar métricas offline como mejora medida en producción.
