# Flujos de atención en el LAB

Esta guía corresponde a **[Recorridos anteriores](http://localhost:5190/?view=flows&mode=inspector&lang=es)**. Para agregar y conectar bloques, consulta el **[editor de flujos e incidencias](editor-flujos-lab.md)**, ahora vista inicial de Flujos. El visor usa **React Flow 12.12.0**, FastAPI, Jev y Luna high. No requiere PostgreSQL para evaluar conversaciones ni utiliza la sesión del banco.

## Decisiones del recorrido

| Etapa | Responsable | Resultado |
| --- | --- | --- |
| Identificar el caso | Jev | Una de las 24 categorías interactivas y su distribución de probabilidades. |
| Elegir el flujo | Regla del servidor | Consulta, problema, servicio o aclaración. Sólo los seis problemas tienen contrato. |
| Revisar el contexto | Luna high | Campos declarados con cita exacta del cliente; contexto consistente, contradictorio o que requiere atención humana. |
| Decidir el siguiente paso | Regla del servidor | Preguntar, revisar en el banco, proponer revisión humana, detener o mostrar error de proveedor. |

La familia se deriva de la categoría de Jev: no es otra inferencia independiente. Luna revisa contexto después de Jev; la comparación independiente de clasificadores permanece en Conversaciones y NLP en Benchmark.

Selecciona un nodo para inspeccionar salidas, citas, probabilidad, tiempo y versión. Las conexiones representan reglas del servidor. Mover nodos sólo cambia su posición en la vista; no se guarda el diseño ni se modifican permisos. En móvil hay un resumen legible de las etapas.

## Probar tres resultados

Selecciona **Conversación personalizada**, pega un mensaje y pulsa **Ejecutar turno**. Revisa Siguiente respuesta y Datos y preguntas. Continúa escribiendo para observar cómo se recalcula el caso y se dejan de preguntar los datos ya declarados. Máximo dos preguntas por turno y diez mensajes por conversación, incluyendo las respuestas del asistente.

| Resultado | Mensaje inicial reconstruido | Qué comprobar |
| --- | --- | --- |
| Preguntar datos faltantes | «Veo un cargo en Librería Central que no reconozco. Quiero revisarlo.» | Cargo no reconocido; preguntar fecha e importe. Responder con esos datos permite proponer revisión en el banco, sin afirmar que se consultó el movimiento. |
| Contexto inicial completo | «El 30 de septiembre de 2026, Librería Central me cobró 120 MXN, pero mi comprobante dice 80 MXN. Reconozco la compra y sólo cuestiono el importe.» | Cobro incorrecto y propuesta de revisar en el banco. No se crea una devolución ni se promete un abono. |
| Atención humana | «La app se cierra al tocar Entrar. Ya reinstalé y reinicié el teléfono. Soporte me pidió repetirlo dos veces y no se resolvió; quiero hablar con una persona.» | Proponer revisión humana y conservar los pasos intentados. No afirmar que un especialista recibió el caso. |

Los ejemplos se construyeron a partir de categorías del dataset; no son transcripciones auténticas de reclamos. Problemas del dataset conserva la evidencia agregada. Las preguntas son una política inicial de evaluación, no procedimientos normativos de un banco específico.

Al ejecutar se envía la conversación visible a los proveedores configurados. Normalmente hay una llamada a Jev y una a Luna; las aclaraciones y fuera de alcance omiten Luna. No hay llamadas al abrir la página, cambiar de caso, editar reglas o recuperar un resultado, ni reintentos automáticos. Un error deja el turno incompleto y permite volver a intentarlo.

## Editar, guardar y comparar

En **Preguntas e instrucciones**, selecciona una de las 24 categorías y edita la redacción en el idioma activo. Las instrucciones adicionales ayudan a interpretar el contexto; los campos requeridos, destinos y permisos siguen fijados en código. Guarda antes de ejecutar para aplicar los cambios al siguiente turno.

Cada guardado incrementa una revisión global. Si otra edición cambió esa revisión, el servidor devuelve conflicto; **Recargar reglas** trae la versión actual. Las ejecuciones conservan una copia de la definición y sus hashes: editar no cambia resultados históricos. Compara variantes iniciando conversaciones nuevas con la misma entrada. Este panel aún no agrega métricas de variantes ni publica reglas al banco.

**Abrir una ejecución guardada** recupera uno de los últimos 30 resultados del idioma activo sin llamar al modelo. Puedes continuar desde ese contexto: conserva el ID de conversación y crea un ID nuevo de ejecución. Recuperar un turno antiguo no recupera turnos posteriores. El tiempo mostrado corresponde a evaluación en servidor, no a un SLA ni a resolución bancaria.

En **Guardar conversación**, escribe un nombre. Después de ejecutar, guarda la entrada del último turno; antes de ejecutar, guarda la entrada del editor. **Descargar trazas JSON** exporta los turnos visibles de la sesión. El historial completo permanece en el servidor local.

| Archivo privado | Contenido |
| --- | --- |
| `.local/intent-lab/flow-config.json` | Preguntas e instrucciones por categoría e idioma; revisión. |
| `.local/intent-lab/conversations.json` | Casos personalizados, compartido con Conversaciones. |
| `.local/intent-lab/runs/{uuid}.json` | Entrada, ID de conversación, clasificación, citas, preguntas, definición usada, hashes y tiempos. |

Sólo el idioma se guarda en localStorage. Los JSON pueden contener conversaciones: están excluidos de Git junto con las credenciales. El LAB sigue siendo local y no tiene identidad administrativa multiusuario; no debe publicarse como panel de administración tal cual.

## API y límites

- `GET /lab-api/flow-map?language=es`: definiciones, contratos y planes de referencia.
- `PUT /lab-api/flow-map/{intent}`: redacción e instrucciones con revisión optimista; rechaza campos nuevos.
- `POST /lab-api/flow-run`: ejecuta un turno de texto con bloqueo de concurrencia de proveedores.
- `GET /lab-api/flow-history?language=es`: hasta 30 ejecuciones recientes del idioma.
- `GET /lab-api/runs/{uuid}`: registro completo, sin ejecución.

Una cita demuestra que el cliente escribió algo; **no demuestra que el hecho sea verdadero** ni que el campo esté interpretado correctamente. Se rechazan citas inexistentes, mensajes del asistente y campos fuera del caso. La extracción de Luna todavía requiere evaluación semántica; el prompt indica conservar como faltantes las respuestas ambiguas o desconocidas, sin garantía de detección infalible.

Contexto completo significa **revisar en el banco**, no evidencia suficiente para operar. No se consultan cuentas, movimientos ni logs. El [evaluador de evidencia bancaria](flujo-evidencia-y-escalamiento.md) completo sigue pendiente. La propuesta humana no abre tickets ni agenda llamadas. Bloqueos, pagos y devoluciones conservan los [controles del banco](acciones-problemas.md).

Cada turno vuelve a clasificar. Cambiar de problema a consulta descarta el contrato y las herramientas de preparación anteriores. Voz, micrófono, selección de voces, acentos y jerga por país quedan para la implementación final pedida por Bryan; no se realizaron pruebas de voz ni se instalaron motores.

## Arranque y comprobaciones

Desde la raíz, con el entorno preparado según el [README del LAB](../experiments/intent-lab/README.md):

```powershell
npm ci
npm run build:lab
$env:PYTHONPATH = "$PWD/experiments/intent-lab"
.local/intent-lab-venv/Scripts/python.exe -m uvicorn intent_lab.api:app --host 127.0.0.1 --port 5190 --no-access-log
```

En otra terminal:

```powershell
$env:PYTHONPATH = "$PWD/experiments/intent-lab"
.local/intent-lab-venv/Scripts/python.exe -m pytest experiments/intent-lab/tests -q
npm run test:lab:flows
```

La prueba de interfaz usa Edge instalado y respuestas controladas: **no gasta API ni llama al banco**. `PLAYWRIGHT_CHANNEL` permite otro canal instalado. Comprueba preguntas editadas, cinco decisiones por idioma, reinicio, móvil y accesibilidad. La API prueba citas, errores, cambios de ruta, contratos, aislamiento, revisiones e historial persistente. Para probar calidad real, usa Ejecutar turno con las claves privadas configuradas; las respuestas no son deterministas.

Validación del 1 de octubre de 2026: 66 pruebas LAB, 116 API bancarias y 12 frontend correctas. Cuatro turnos reales ES/EN/PT coincidieron con categoría y estado esperados: solicitud de datos, revisión de contexto completo, propuesta humana y continuación que completó los datos faltantes. Tiempos entre **3,53 y 5,71 segundos**. Son comprobaciones puntuales con textos ficticios, no métricas representativas de precisión o latencia. Resultados completos privados en `.local/intent-lab/flow-live-verification.json`.
