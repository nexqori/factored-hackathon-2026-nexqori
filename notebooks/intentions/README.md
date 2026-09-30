# Limpieza y análisis inicial de intenciones

Abrir `INTENTIONS_EDA.ipynb`: contiene el código Python, resultados ejecutados, gráficos y conclusiones. Fuente local predeterminada: carpeta hermana `nexqori-dataset`; puede sustituirse con `NEXQORI_DATASET_DIR` o `DATASET_OVERRIDE` en el notebook. No conecta con AWS ni con modelos externos.

Perfil completo de todas las tablas CSV encontradas: archivos/rutas, esquemas, filas, nulos, blancos, tipos esperados y conversiones inválidas, claves duplicadas y filas duplicadas, cobertura temporal. Análisis de intención concentrado en transcripciones, interacciones, reclamos y encuestas. No confunde categorías históricas con etiquetas fiables ni acento con idioma.

Instalar desde la raíz: `.venv-app/Scripts/python.exe -m pip install -r requirements-eda.txt`. Abrir el notebook con ese entorno y ejecutar todas las celdas. Generador reproducible: `crear_notebook.py`. Ejecutor sin registrar kernels globales: `ejecutar_notebook.py`. Regenerar sustituye el notebook; ejecutar recalcula sobre los CSV reales. Los originales nunca se escriben.

- `results/`: perfiles y agregados CSV, conclusiones Markdown, manifiesto de ejecución y comprobaciones.
- `figures/`: gráficos PNG, también incrustados en el notebook.
- `private/`: manifiesto con huellas/rutas, copias limpias de las cuatro tablas de atención y corpus de candidatos. **Datos locales excluidos de Git**, no publicar ni enviar a proveedores.
- `runtime/`: caché DuckDB y temporales, excluidos de Git. Límites: 1500 MB de DuckDB y cuatro hilos; Python y sistema pueden usar memoria adicional. CPU, sin requerir GPU.

La limpieza conserva IDs, acentos, negaciones y significado; sólo normaliza Unicode/espacios en textos y convierte vacíos en nulos. Conserva todas las filas y marca duplicados textuales, sin borrar interacciones válidas por compartir plantilla. No entrena un modelo ni garantiza calidad de las etiquetas. Resultados publicados deben revisarse: los perfiles agregados no contienen transcripciones ni IDs, pero el notebook documenta la ruta local solicitada.
