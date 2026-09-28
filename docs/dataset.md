# Dataset del Factored AI & Data Hackathon 2026

Script para descargar el dataset oficial desde Amazon S3 a `dataset/`, conservando
los CSV originales y sus particiones. Funciona en Windows, macOS y Linux con
Python 3.9 o posterior y AWS CLI v2 instalado y disponible en el PATH.
No necesita paquetes adicionales de Python.

## Acceso

Cada participante debe obtener las credenciales de solo lectura del organizador.
Las credenciales no estan incluidas en este repositorio. Configura un perfil local:

```sh
aws configure --profile factored-hackathon
```

Introduce las credenciales recibidas, la region `us-east-2` y salida `json`.
Tambien puedes usar las variables de entorno estandar de AWS o un perfil ya existente.
El script no modifica la configuracion global de AWS ni guarda claves en sus archivos.

## Descargar

Desde la raiz del proyecto:

```sh
python scripts/descargar_dataset.py --profile factored-hackathon
```

En sistemas donde Python se llama `python3`, usa ese comando. Si usas credenciales
en variables de entorno, omite `--profile`.

La descarga empieza por las tablas base, despues reclamos, interacciones,
transcripciones y encuestas. Continua con transacciones, envios de campanas y
eventos digitales. Los archivos terminados se pueden consultar mientras sigue
la descarga; evita los archivos temporales de AWS CLI.

El inventario observado el 25 de septiembre de 2026 tiene **7.671 archivos y
5.349.322.481 bytes (5,35 GB)**. El script vuelve a consultar S3 en cada ejecucion,
comprueba espacio libre y conserva un inventario de esa ejecucion.

Si se interrumpe, vuelve a ejecutar el mismo comando: conserva los archivos completos
segun las comprobaciones de tamano y sincronizacion de AWS CLI. Una transferencia
individual incompleta puede comenzar de nuevo. No se eliminan archivos locales.
Las credenciales deben seguir vigentes para continuar.

## Consultar avance

```sh
python scripts/descargar_dataset.py --status
```

Lee el ultimo estado local, actualizado aproximadamente cada diez segundos durante
las transferencias. Incluye archivos y bytes disponibles por tabla. No conecta con AWS.
Si el proceso se termina abruptamente, la fecha del estado permite detectar que dejo
de actualizarse; `descargando` por si solo no confirma que el proceso siga vivo.

```text
dataset/
  branches.csv
  customers.csv
  products.csv
  ...
  call_center_interactions/year=2023/month=06/day=17/...
  call_transcripts/...
  complaints/...
  transactions/...
  ...
  _descarga/
    inventario-s3.json
    progreso.json
    transferencias.log
```

`completado` significa que todos los archivos del inventario existen y coinciden en
tamano. No equivale a validar sus filas, esquemas o integridad criptografica.

## Opciones

```sh
python scripts/descargar_dataset.py --profile factored-hackathon --inventory-only
python scripts/descargar_dataset.py --profile factored-hackathon --destination /ruta/dataset
python scripts/descargar_dataset.py --help
```

Se pueden cambiar `--bucket`, `--prefix` y `--region` si el organizador cambia el origen.
Para consultar otra carpeta, combina `--status` con `--destination`.

## Archivos para GitHub

Comparte `scripts/descargar_dataset.py`, este `README.md` y `.gitignore`.
`dataset/` esta excluido de Git. Tambien se excluyen archivos de credenciales y el PDF
del diccionario que contiene claves de acceso. No publiques ese PDF ni claves AWS.
El acceso al dataset sigue restringido a quienes autorice el organizador.

## EDA integral con GPU

El [notebook ejecutado](../notebooks/EDA_PROBLEMAS.ipynb) contiene resultados,
diez gráficos, denominadores y limitaciones. También hay una
[versión HTML de lectura](../notebooks/EDA_PROBLEMAS.html) que no requiere Python.

El análisis actual examina todas las filas y columnas de las 13 tablas:
**23.495.188 registros, 7.671 CSV y 5.349.322.481 bytes**. Sustituye el muestreo
inicial. Incluye quejas, problemas técnicos, SLA, transcripciones, transacciones,
eventos digitales, encuestas, clientes, productos, sucursales, agentes, campañas
y tipos de cambio. El notebook guarda los resultados y un anexo desplegable con
todas las tablas agregadas completas; se puede leer sin recalcular.

Se utilizó la RTX 3050 Ti Laptop de 4 GB: CuPy/CUDA calcula perfiles de 42 campos
numéricos por bloques de 131.072 filas, con un pool limitado a 192 MiB. DuckDB
procesa CSV, texto, uniones y agregaciones categóricas en CPU. No se carga el
dataset entero en RAM o VRAM. Todos los perfiles numéricos se contrastan contra
CPU sobre sus valores completos. Primera preparación: 724,40 segundos y pico
RSS observado de 2.049,46 MiB; incluye preparación/consultas y compilación inicial
CUDA, pero no la validación posterior. No es un benchmark de aceleración GPU/CPU.

Para reproducirlo, desde la raíz del proyecto, con Python 3.12, el dataset
descargado y GPU NVIDIA con controlador compatible con CUDA 12:

```sh
python -m venv .venv
```

Activa `.venv` (`.venv\Scripts\Activate.ps1` en PowerShell o
`source .venv/bin/activate` en macOS/Linux) y ejecuta:

```sh
python -m pip install -r requirements-eda-gpu.txt
python scripts/ejecutar_notebook_eda.py
```

También puedes abrir el notebook en Jupyter o VS Code, seleccionar ese entorno
y ejecutar todas las celdas. Para regenerar el documento desde su plantilla:

```sh
python scripts/crear_notebook_integral.py
python scripts/ejecutar_notebook_eda.py
```

La instalación usa las dependencias CUDA de la rueda de CuPy en el entorno local;
consulta la [documentación oficial](https://docs.cupy.dev/en/stable/install.html)
si tu plataforma/controlador necesita otra versión. El análisis requiere GPU
real y falla explícitamente si no está disponible; leer las salidas guardadas
no requiere GPU ni Python.

La primera ejecución prepara las 13 tablas; después reutiliza una caché local
en `dataset/_eda_integral/` y recalcula agregados. La huella usa rutas, tamaños,
fechas de modificación y configuración; no es un hash del contenido de los CSV.
Para forzar una nueva lectura de **todo el dataset**, usa `REBUILD=True` en el
notebook o `python scripts/eda_integral.py --rebuild`. El motor tiene un límite
de memoria DuckDB de 1.500 MB y cuatro hilos; Python puede usar memoria adicional.

Las consultas auditables están en `sql/eda/`, `sql/eda_detalle/` y
`sql/eda_integral/`; la preparación en `scripts/eda_integral.py` y las 79
comprobaciones en `scripts/validar_integral.py`. Que estas comprobaciones pasen
confirma las mediciones, no que los datos carezcan de problemas.
`notebooks/resultados_integral/` contiene agregados y
`notebooks/figuras_integral/` los gráficos; las filas originales y la caché
quedan dentro de `dataset/`, excluido de Git. `primera_ejecucion.json` conserva
la medición inicial; `ejecucion.json` registra el recálculo más reciente.
Los scripts `eda_problemas.py`, `eda_detalle.py` y `crear_notebook_eda.py`, y las
carpetas `resultados/` y `figuras/`, son antecedentes exploratorios; no definen
el alcance del notebook integral actual.
No se publican nombres, contactos, transcripciones ni credenciales en las salidas.

Las conclusiones describen datos sintéticos históricos. `sla_breached` es una
etiqueta, no una verificación contractual.
La ausencia de `origin_interaction_id` en todos los casos impide enlazarlos
directamente con conversaciones. Los 44.570 casos con producto asociado apuntan
a un producto cuyo titular es otro cliente; 149.995 de 150.000 referencias de
sucursal de registro no encuentran padre. Ambos hallazgos se comprobaron de
nuevo leyendo directamente los CSV. Las 171.321 transcripciones mencionan saldo
y sólo tienen 42 variantes exactas de texto del cliente; sus etiquetas no bastan
para entrenar una clasificación fiable de quejas. Ese EDA no implementaba una app; la base Nexqori posterior está descrita en el README principal.
