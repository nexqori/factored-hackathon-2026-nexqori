# Conclusiones del análisis inicial

- Fuente real: `C:\Users\santi\Documents\Projects\nexqori-dataset`. Censo de 7,671 CSV, 13 tablas, 23,495,188 filas y 260 columnas sumadas entre tablas.

- Calidad estructural: 0 filas duplicadas exactas adicionales; 0 repeticiones adicionales de clave no nula; 29.82% de celdas nulas/vacías. Un valor nulo no es automáticamente un error de negocio.

- Conversiones inválidas no vacías: 0. Tipos esperados son reglas semánticas; los CSV se preservan como texto.

- Transcripciones: 171,321 textos de cliente disponibles; 42 variantes limpias exactas; 171,321 mencionan saldo. La repetición limita la diversidad para evaluar nuevas intenciones.

- Los meses inicial y final pueden ser parciales; no comparar sus conteos como meses completos. Cobertura temporal detallada en temporal_coverage.csv; process_date y fecha del evento no son equivalentes. No se conoce zona horaria ni disponibilidad histórica exacta de desenlaces.

- Idioma declarado en transcripciones: es: 171,321. Acento no acredita idioma; los indicios léxicos son exploratorios.

- No se observó portugués declarado en las transcripciones; no afirmar cobertura PT a partir de este corpus.

- Comparar text_vs_reason.csv antes de usar etiquetas: mencionar saldo bajo otra categoría no prueba por sí solo cuál etiqueta sería correcta, pero exige revisión. No entrenar con reason_category o detected_intents sin validar.

- Conservar grupos de textos y traducciones juntos al dividir desarrollo/validación/test; no dividir al azar las filas repetidas.

- Crear un conjunto revisado ES/PT y regresión EN con ambiguas, negaciones, varias intenciones y derivación humana. Identificar ejemplos del equipo y del organizador por separado.

- Las sugerencias del baseline no tienen probabilidad calibrada ni miden exactitud. No se llamó a Jev/LLM ni se entrenó un modelo.

- Validación: 21 controles satisfactorios. La app no fue modificada. Derivados individuales sólo en private/; no publicar ni enviar externamente.
