# Nexqori · Laboratorio de intención

Contratos de problemas v2: sólo las seis categorías de problemas cargan procedimiento e instrucciones para Luna. Consultas y solicitudes de servicios se enrutan aparte; una consulta no activa el contrato de reclamos. La clasificación interactiva incluye 24 etiquetas: `request-status` abre Mis solicitudes como consulta y no ofrece devolución. El benchmark NLP conserva sus 23 etiquetas y 345 ejemplos; no mide todavía esta nueva categoría. Para cargos elegibles, el LAB muestra accesos a bloqueo y revisión de devolución dentro del banco autenticado; no ejecuta herramientas bancarias. Ver [acciones y controles](../../docs/acciones-problemas.md) y [evaluación de segunda atención](../../docs/evaluacion-segunda-atencion.md).

Abre **http://localhost:5190/**. El banco principal sigue en **http://localhost:5180/**. Este laboratorio no comparte sesiones, operaciones ni base de datos con el banco.

## Qué se puede hacer

- Elegir cinco conversaciones representativas: cargo no reconocido, cobro indebido, problema con la app, atención en sucursal y calidad de servicio. Los diálogos están diseñados para evaluar; las categorías y sus frecuencias vienen del censo del dataset sintético.
- Crear o personalizar una conversación, elegir una etiqueta esperada y guardar. **`.local/intent-lab/conversations.json`** conserva los casos al reiniciar. Se pueden reabrir, actualizar y descargar; las claves y el dataset quedan fuera de ese archivo. Máximo 100 conversaciones, 10 mensajes por conversación y 2.000 caracteres por mensaje. Terminar con un mensaje del cliente.
- Editar instrucciones: prompt general, criterio bancario v1 o texto propio. Las conversaciones guardadas conservan el prompt; también se puede descargar una variante. Cambiar la entrada invalida la salida visible anterior.
- Pulsar **Ejecutar caso**: una llamada real a Jev y otra a Luna, con la conversación y las instrucciones visibles. Ambos clasifican de forma independiente. La respuesta muestra intención, distribución, confianza, tiempo total de la llamada, revisión del modelo y consumo. No hay reintentos automáticos. Se guarda el registro local en `.local/intent-lab/runs/{id}.json`, sin credenciales.
- LLM conectado: GPT-6 Luna con razonamiento **high**. La clasificación independiente se separa de **Conversar con el contrato**, donde Jev elige el caso y Luna redacta la respuesta. Acuerdo entre modelos sigue siendo una propuesta para revisión; no autoriza operaciones.
- Explorar acuerdo/desacuerdo/error/incertidumbre en la **vista esperada**, identificada como referencia. Esos estados no son inferencias de modelos.
- Consultar cinco **textos originales del dataset**, sin reescribir, en una sección aparte. Son ejemplos sintéticos de consultas de saldo con marcadores incompletos en el texto del agente; no son conversaciones auténticas de clientes. Se sirven desde `.local/intent-lab/original-transcripts.json`, excluido de Git. La UI de originales es de lectura local y no los envía a proveedores.
- Consultar el mapa completo de las subcategorías de reclamos, motivos generales de contacto, errores por acción digital y rutas permitidas. Los denominadores corresponden a poblaciones distintas; no se suman.

## Clave de Jev

Crear el archivo privado **`.local/intent-lab/providers.env`** usando `providers.env.example` como referencia:

```dotenv
TYPESAFE_API_KEY=
JEV_MODEL=jev-1.13.0
```

Pegar la clave después de `=`. El servidor lee este archivo en cada ejecución; no hace falta reiniciarlo al cambiar la clave. La API sólo devuelve si hay una clave configurada, nunca su valor. No pegarla en instrucciones, conversaciones ni parámetros del navegador. El modelo elegido es `gpt-6-luna`, razonamiento `high` ([ficha oficial](https://developers.openai.com/api/docs/models/gpt-6-luna), verificada el 30/09/2026). Configura también `LLM_API_KEY`, `LLM_MODEL=gpt-6-luna` y `LLM_REASONING_EFFORT=high`. La conexión está implementada y autorizada: al ejecutar se envían sólo las entradas visibles del LAB a los proveedores oficiales. No cambies de modelo ante un error sin decidirlo explícitamente.

Contrato oficial: [API de TypeSafe](https://docs.typesafe.ai/api). La [confianza](https://docs.typesafe.ai/confidence) y la probabilidad de la opción se conservan por separado; ninguna se muestra como acierto medido. El coste indicado usa la tarifa pública de [Jev 1.13](https://docs.typesafe.ai/models) consultada el 29/09/2026, 0,042 USD por millón de tokens de entrada; es una estimación, no una factura.

## Arranque local desde la raíz del repositorio

Node 24, Python 3.12 y las dependencias frontend del repositorio. No requiere motores de voz, GPU ni PostgreSQL.

```powershell
npm ci
py -3.12 -m venv .local/intent-lab-venv
.local/intent-lab-venv/Scripts/python.exe -m pip install -r experiments/intent-lab/requirements.lock
node node_modules/typescript/bin/tsc -p experiments/intent-lab/tsconfig.json --noEmit
node node_modules/vite/bin/vite.js build --config experiments/intent-lab/vite.config.ts
$env:PYTHONPATH = "$PWD/experiments/intent-lab"
.local/intent-lab-venv/Scripts/python.exe -m uvicorn intent_lab.api:app --host 127.0.0.1 --port 5190 --no-access-log
```

La preferencia de idioma es el único dato en localStorage. Las conversaciones y ejecuciones permanecen en `.local/intent-lab`; `NEXQORI_LAB_DATA` permite elegir otra carpeta privada desde el entorno del servidor.

## Datos y evaluación

`audit_source.py` regenera `evidence.json` desde agregados ya censados. No vuelve a leer filas individuales. Para cargar los cinco originales en un equipo que tenga el dataset y el entorno EDA:

```powershell
.venv/Scripts/python.exe experiments/intent-lab/extract_originals.py
```

La consulta es DuckDB de sólo lectura y selecciona cinco textos distintos intercalando las dos familias de saldo. Conserva un par cliente/agente de la misma transcripción; frecuencia y selección no implican representatividad de todos los problemas.

El benchmark NLP usa **345 ejemplos**: 138 entrenamiento, 69 validación, 138 prueba; 23 etiquetas y ES/EN/PT. Son casos diseñados y definiciones del catálogo, pendientes de revisión humana. Las traducciones y familias no cruzan particiones, y se rechazan textos normalizados duplicados entre ellas. La validación está reservada; no se usó para calibrar ni seleccionar hiperparámetros. Los cinco recorridos conversacionales y los casos personalizados están separados de este lote.

Dos referencias básicas: TF-IDF de caracteres + centroides/coseno; TF-IDF + regresión logística. Se mide acierto, F1 macro, exactitud balanceada, p50/p95, confusión, cortes por idioma/dificultad y calibración sólo cuando existe distribución probabilística. La similitud coseno no se trata como probabilidad. Los costes locales de cómputo no están calculados.

```powershell
$env:PYTHONPATH = "$PWD/experiments/intent-lab"
.local/intent-lab-venv/Scripts/python.exe -m intent_lab.benchmark --output .local/intent-lab/baseline.json
.local/intent-lab-venv/Scripts/python.exe -m pytest experiments/intent-lab/tests -q
node experiments/intent-lab/check-ui.mjs
```

La prueba UI usa Edge headless y guarda un único caso identificado como **Verificación · conversación LAB**; se actualiza en ejecuciones posteriores. Sus capturas y comprobaciones quedan en `.local/intent-lab/verification`. La prueba UI ordinaria no llama proveedores; el botón real se verifica por separado con una solicitud explícita.

Resultado inicial Windows/CPU: centroides 47,10 % de acierto y 44,63 % F1 macro; regresión 44,93 % y 42,11 %. Son referencias sobre este lote pequeño provisional, no resultados bancarios reales ni evidencia de superioridad de Jev. Una única llamada de Jev acertó el caso de cobro duplicado; no constituye un benchmark de Jev.

Para medir mejora de prompt/skill: revisar etiquetas, separar nuevos casos reservados, fijar versiones, ejecutar las mismas entradas en cada alternativa y comparar errores emparejados por idioma. Registrar cambios de protocolo y conservar resultados anteriores. La doble validación debe medir también cobertura, desacuerdos, errores en los que ambos coinciden, fallos de proveedor y coste/latencia total. La autoevaluación de un modelo no sustituye las etiquetas revisadas.

## Alternativas locales investigadas

Jev oficial se sirve por API; sus SDK abiertos no publican pesos del modelo. [OpenJev independiente](https://huggingface.co/openjev/openjev) tiene 27B y GGUF Q4 de 16,5 GB, demasiado para la GPU actual de 4 GB. No es el mismo Jev. [Laya Multilingual](https://huggingface.co/convaiinnovations/laya-multilingual) (322M, pesos 644 MB) y [Qwen3-1.7B GGUF](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/tree/main) (Q8_0, 1,83 GB) son candidatos posteriores; todavía no descargados ni ejecutados. El encaje de runtime/VRAM y la calidad ES/EN/PT quedan por medir. Por decisión actual, el recorrido usa Jev + LLM; NLP permanece sólo como referencia de benchmark.

## Contratos, diálogo y trazabilidad

Consulta [registro, auditoría y conversación](../../docs/registro-auditoria-y-conversacion.md). El LAB permite editar instrucciones por caso, contexto declarado, diálogo con Jev → contrato → Luna y revisar ejecuciones JSON. El actor es operador local, no un usuario bancario autenticado. La prueba inicial de los cinco diálogos acertó 5/5 etiquetas con cada modelo; no demuestra superioridad ni sustituye el benchmark reservado.
