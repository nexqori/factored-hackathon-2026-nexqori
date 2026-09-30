# Lectura de los resultados

Todos los conteos se calculan sobre archivos locales reales. Las salidas son agregados; no contienen transcripciones, nombres de clientes ni IDs individuales.

| Archivo | Qué permite revisar |
| --- | --- |
| files.csv / schema_variants.csv | Tablas, archivos, bytes, rutas relativas y variantes de cabecera. |
| table_quality.csv | Filas, columnas, celdas ausentes, claves y filas duplicadas. |
| column_profile.csv | Las 260 columnas sumadas entre tablas: descripción, tipo analítico, nulos, blancos y conversiones inválidas. |
| temporal_coverage.csv / day_coverage.csv / monthly_activity.csv | Fechas mínimas/máximas, días observados, huecos y actividad mensual; fecha de proceso separada de evento. |
| cleaning_audit.csv | Transformaciones aplicadas por campo, sin modificar el origen. |
| text_quality.csv / text_concentration.csv | Cobertura de texto, variantes y concentración por fuente. |
| declared_languages.csv / language_hints.csv | Idioma declarado frente a indicios léxicos exploratorios, no equivalentes. |
| transcript_links.csv / transcript_availability.csv | Existencia del vínculo a interacción/cliente y concordancia del indicador de transcripción. |
| recorded_intent_labels.csv / contact_reasons.csv / text_vs_reason.csv | Etiquetas del origen y su relación con evidencia textual; no son verdad validada. |
| baseline_intents.csv | Sugerencias del clasificador actual, ponderadas por frecuencia; no probabilidades ni exactitud. |
| validation.csv / independent_validation.json | Controles del notebook y contraste con otro parser sobre las tres fuentes textuales. |
| run.json | Versiones, huellas de procedencia, alcance y tiempo de ejecución completa. |
| CONCLUSIONES.md | Hallazgos y límites para preparar detección de intenciones. |

Las copias limpias y el corpus individual están en `../private/`, fuera de Git. Esas fuentes no deben confundirse con fixtures de las cuentas de la aplicación. No se ha conectado un proveedor externo ni entrenado un modelo.
