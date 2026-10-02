# Flujos de atención: casos, preguntas y acciones

Abre [Flujos de atención](http://localhost:5190/?view=flows&mode=editor&lang=es). El lienzo ocupa la pantalla; los casos y bloques están a la izquierda y la configuración aparece a la derecha al seleccionar un paso. FastAPI valida e interpreta **el grafo guardado**. Cambiar una conexión cambia la ruta que se ejecuta.

## Empezar con un problema

1. Se abre **un único Flujo de atención** guardado. En **Casos**, elegir un problema carga sólo su conversación y parámetros en Inicio; conserva los bloques, conexiones y cambios del editor.
2. En Inicio, revisa **Procedimiento del caso** y edita el mensaje. Es el procedimiento esperado del ejemplo: Jev decidirá la clasificación real. **Nueva conversación** borra el contexto de la prueba anterior.
3. Pulsa **Flujo completo** en Inicio o en la barra superior. Guarda y valida automáticamente antes de ejecutar. Si falta una conexión, indica el bloque y la salida que debes corregir; no llama modelos con un grafo inválido.
4. El bloque único **Consulta o problema · Jev** clasifica y deriva directamente a **problema/reclamo, consulta/gestión o aclaración**. El problema pasa por identificación del problema y **Derivar según el caso**, con seis salidas hacia sus contratos visibles. Sólo la rama clasificada carga instrucciones, pasos, preguntas y datos necesarios; las demás permanecen sin recorrer. Las consultas tienen su propia clasificación y herramientas; no cargan contratos de problemas ni llaman a Luna para recoger evidencia de un problema.
5. El bloque en ejecución muestra un indicador. Las ramas **Sí** recorridas se ven verdes y las **No**, ocres; las no recorridas permanecen grises. En **Ejecución** aparecen el caso, contrato real, salida, tiempo y pasos realizados. Pulsa un paso para revisar **Resultado**, con explicación simple, o **JSON · detalle**. El inspector tiene un botón para ampliar su ancho.
6. Si faltan datos, se abre la conversación con las preguntas y el estado **Esperando tu respuesta**. Al responder y continuar, la conexión discontinua vuelve a Contexto y a la comprobación de datos. Conserva Jev y el contrato iniciales: no vuelve a clasificar por cada fecha o importe. Repite hasta completar los datos, requerir una persona o llegar al límite de diez respuestas adicionales.

### Ejecutar por bloques

- **Paso a paso** ejecuta Inicio y se detiene. El estado muestra el bloque siguiente.
- Pulsa **▶** bajo el bloque pendiente, en la salida recorrida del bloque anterior o en **Ejecutar siguiente bloque**. La continuación usa el siguiente bloque decidido por el servidor; no permite forzar Sí/No ni ejecutar una rama sin sus entradas.
- **Seleccionar un bloque consulta su último resultado**. Moverlo, renombrarlo, abrir parámetros o salidas, buscar categorías y guardar el diseño conservan el checkpoint y no llaman modelos. El panel indica el resultado guardado y el tiempo de ese bloque.
- Para recalcular un bloque ya recorrido, pulsa expresamente su **▶ / Volver a ejecutar bloque**. Usa las entradas que tenía antes de su última ejecución y corre sólo ese bloque. Conserva los pasos anteriores como **Resultado reutilizado** y descarta los resultados posteriores de esta nueva continuación para no mezclar derivaciones. Se guarda una ejecución nueva vinculada a la anterior, que permanece intacta. Si el bloque usa Jev o Luna, esta acción sí vuelve a llamar al proveedor.
- **Flujo completo** continúa desde ese punto hasta la siguiente pregunta, resultado o error. No repite los bloques ya terminados.
- El enlace conserva `workflow` y `execution`. Recargar recupera el resultado y el punto de continuación **sin llamar a modelos**. Si sigue en curso, usa **Recuperar ejecución** para consultar el estado al terminar.
- Cambiar instrucciones, condiciones, bloques o conexiones conserva los resultados y pausa la continuación: **Restaurar reglas de la ejecución** permite seguir; **Nueva conversación** aplica los cambios en otra evaluación. Cambiar sólo posiciones, nombres o etiquetas y guardar una revisión permite continuar con las reglas originales. Si el proceso se interrumpió durante una llamada, no se reintenta automáticamente: queda señalado y se empieza otra conversación.
- La columna **Funciones que se activarían** muestra **Se activaría**, función y requisitos. Los bloques de acción, especialista, seguimiento y cierre usan un borde discontinuo y preparan propuestas, sin ejecutarlas. Completar los datos del cliente no acredita una transacción ni ejecuta una devolución. La devolución conserva revisión de evidencia, titularidad, confirmación y aprobación administrativa.

### Casos disponibles y procedencia

| Problema | Procedencia | Procedimiento inicial |
| --- | --- | --- |
| Cargo no reconocido | 12.297 reclamos | Identificar movimiento, contrastar datos, revisar protección y posible devolución. |
| Cobro incorrecto | 12.194 reclamos | Recoger importe/fecha, contrastar cargo y revisar devolución. |
| Pago pendiente o rechazado | Alcance acordado, sin frecuencia directa de reclamos | Identificar intento y estado antes de proponer otro pago. |
| Problema con la app | 12.128 reclamos | Recoger síntoma/intentos; mostrar correlación de logs y aviso condicionado a un error confirmado. |
| Atención en sucursal | 11.892 reclamos | Recoger visita y motivo, preparar revisión de atención. |
| Experiencia de atención | 11.886 reclamos | Registrar contexto de atención y preparar seguimiento. |

Los conteos proceden de [evidence.json](../experiments/intent-lab/evidence.json), sobre 67.095 reclamos; son registros, no clientes únicos. Los seis contratos vienen del [catálogo de procedimientos](../backend/workflow_catalog.json). **Consultas y otros alcances** contiene las 18 categorías restantes: 24 en total. El buscador filtra casos y bloques. Elegir un caso no fuerza la clasificación: Jev decide según los mensajes enviados.

Los cinco escenarios conversacionales son ejemplos redactados basados en las categorías. Las demás categorías incluyen una pregunta inicial. El procedimiento indica esta procedencia; no se presentan como transcripciones auténticas. El flujo compartido reúne las seis ramas en Contexto y después pregunta, prepara derivación o propone acción, resultado y cierre. Seguimiento de reclamo sin problema nuevo usa la consulta `request-status`. El mapa funcional acordado está en [flujo maestro de atención](flujo-maestro-atencion.md).

En los bloques de clasificación y derivación, **Casos y subdivisiones** presenta el catálogo completo: seis problemas, ocho consultas, siete servicios y tres categorías de aclaración. Se puede buscar, filtrar **En este bloque** y desplegar requisitos, procedimiento y funciones de cada caso. Señala la clasificación guardada y muestra porcentajes sólo cuando los devuelve el proveedor. Explorar este catálogo no carga otro ejemplo ni cambia la conversación. La primera clasificación sigue decidiendo sólo la familia; el catálogo es una referencia de sus posibles derivaciones.

## Consultar registros del usuario de prueba

En Inicio, abre **Registros del banco**, consulta la sesión bancaria del mismo navegador y elige un movimiento propio. Contexto completará los datos disponibles y mostrará qué falta preguntar. La [guía de contexto bancario](contexto-bancario-en-flujos.md) incluye los tres casos persistentes, los accesos privados, los límites y `npm run test:lab:bank`. Las lecturas quedan auditadas; las operaciones siguen como propuestas.

## Crear y ajustar un flujo

1. Abre **Mis flujos** con la carpeta de la barra superior. Puedes recuperar un flujo o crear uno desde cero, con Plantilla bancaria o con Incidencia de la app.
2. Usa el **+** del lienzo para abrir Bloques y arrastra una tarjeta a un espacio libre. El **+ de una conexión** inserta un bloque entre dos pasos, conservando la continuación; el **+ de una salida libre** conecta el paso nuevo. También puedes arrastrar una salida al espacio vacío para elegir el siguiente bloque.
3. Haz clic en un bloque para editarlo en el panel derecho. Une sus puntos o arrastra el extremo de una conexión para cambiar el destino. También puedes elegir el destino en **Conexiones de salida**, útil con teclado y en móvil. Tab/Enter selecciona los bloques y abre su configuración.
4. Las condiciones tienen salidas **Sí** y **No**. Conecta ambas. Insertar una condición conserva la continuación por Sí y deja No pendiente de conectar. Un bloque terminal (Pregunta, Respuesta o Revisión humana) se añade al lienzo o a una salida libre; no se inserta sobre una conexión existente porque cortaría su continuación. **Deshacer/Rehacer** recupera ediciones y movimientos; **Ordenar bloques** distribuye el grafo por niveles.
5. **Validar conexiones** indica el bloque que falta conectar o el requisito que falta en esa ruta. Se pueden guardar borradores incompletos; no se pueden ejecutar hasta corregirlos. Elimina los bloques que sobren desde su panel.
6. **Guardar borrador** crea una revisión y actualiza el enlace del navegador para recuperar ese flujo. Cambia Español / English / Português para editar el texto de ese idioma; cambiar de idioma conserva el borrador abierto.

**Duplicar** crea una variante pendiente de guardar. **Exportar JSON** descarga la definición completa para compartirla; **Importar JSON** la valida y abre como otro borrador. Revisa el contexto antes de compartir: puede contener lo que hayas escrito. Las claves se configuran únicamente en el archivo privado de proveedores.

El guardado utiliza revisión optimista. Si otro editor guardó antes, recarga el flujo y vuelve a aplicar los cambios. La biblioteca tiene un máximo de 50 flujos locales. Las rutas automáticas son acíclicas, con un solo Inicio, hasta 40 bloques y 64 conexiones. La salida opcional Respuesta del cliente de una Pregunta sólo puede volver a un Contexto previo presente en todas las rutas que llegan a ella; espera un mensaje real o una referencia bancaria nueva y no admite bloques intermedios con +. Cada salida admite un destino; se permiten varias entradas al mismo bloque. Cada ruta debe haber pasado por sus requisitos: por ejemplo, Contexto según el caso necesita Jev, y Aviso local necesita Recoger logs.

## Bloques disponibles

| Bloque | Configuración y efecto |
| --- | --- |
| Inicio | Recibe mensajes e idioma del turno. |
| Consulta o problema · Jev | Clasifica y deriva con tres salidas: problema, consulta/gestión o aclaración. Máximo uno. Reemplaza clasificación + condición inicial; los flujos antiguos conservan compatibilidad. |
| Clasificación Jev | Clasifica el caso entre las categorías permitidas de su rama. Hasta dos bloques en ramas excluyentes, uno por recorrido. Un clasificador con alcance problema/consulta requiere la derivación previa. |
| Rutas por problema | Seis salidas de contrato y una de aclaración. El servidor selecciona la salida según Jev. |
| Contrato del caso | Carga el contrato y configuración del problema que Jev identificó. Hasta seis en ramas distintas, uno por recorrido. Un contrato fijo que no coincide con Jev detiene el flujo. |
| Activación propuesta | Etapa consulta, acción, derivación, resultado o cierre. Devuelve funciones permitidas y requisitos, siempre `executed: false`; sin adaptadores ejecutables. |
| Contexto · Luna | Elige campos según Jev o una lista explícita. Admite instrucciones y referencia no verificada. Extrae citas exactas del cliente y puede combinar registros autenticados del banco, sin enviarlos al modelo. Muestra preguntas, fuentes y auditoría. Máximo uno. |
| Condición | Compara intención, familia, datos faltantes, necesidad de atención humana o error registrado en los logs. |
| Pregunta | Pide hasta dos datos faltantes o una pregunta personalizada. Con salida Respuesta del cliente conectada, espera y reanuda el contexto al recibirla. |
| Respuesta | Termina con información, propuesta de revisión o conserva el resultado de la ruta recorrida. Texto por idioma. |
| Revisión humana | Propone la intervención de una persona y termina el turno. No contacta a nadie. |
| Recoger logs | Lee la incidencia local vinculada a la comprobación de acceso. Máximo uno. |
| Aviso local | Registra una notificación en Avisos de incidencias, con referencia correlacionada. |

No se aceptan bloques de código, SQL, URLs de ejecución, claves ni comandos bancarios libres. Las lecturas autenticadas usan exclusivamente el adaptador cerrado de Contexto. Los modelos se llaman sólo si la ruta pasa por su bloque: en el flujo maestro, dos llamadas a Jev al iniciar (familia y caso), más Luna sólo si llega a Contexto. Cada respuesta sobre datos faltantes vuelve a Contexto y llama a Luna una vez, conservando Jev. El modo por pasos sólo consume la llamada del bloque que se ejecuta. Abrir, mover, validar, guardar e importar no llama a proveedores. No hay reintentos automáticos. Un error del proveedor detiene la ruta y queda en la traza.

## Probar el error de acceso, sin consumir modelos

1. Crea un flujo con **Incidencia de la app**. El botón de ejecución lo guardará automáticamente.
2. Haz clic en **Inicio** y pulsa **Reproducir error de acceso**. El servidor ejecuta una comprobación controlada que lanza y captura un fallo de carga de sesión. Crea un ID y una referencia `APP-…`.
3. Pulsa **Flujo completo**. El recorrido será Inicio → Recoger logs → ¿Se confirmó el error? → Aviso local → Confirmar el aviso.
4. Selecciona Recoger logs en la traza: verás inicio de comprobación, error `session_load_timeout`, marca de tiempo y referencia común. El código 503 forma parte del registro de prueba; no es una caída del servidor bancario. `timeout_budget_ms` es el presupuesto configurado del caso, no latencia medida.
5. Abre **Avisos de incidencias** abajo. La referencia coincide con la de los logs. Repite un turno con la misma incidencia: se conserva el aviso existente, sin duplicarlo. Una nueva comprobación crea otra incidencia.

Esta plantilla no tiene bloques de modelos y funciona sin API keys. Si ejecutas sin vincular una incidencia, se detiene pidiendo la comprobación. No infiere la existencia de logs a partir de lo que diga el cliente. La rama No está preparada para un registro sin fallo; el botón actual produce siempre el fallo controlado.

El **Flujo de atención** predeterminado muestra lo que se activaría para el problema de la app; no ejecuta esta comprobación ni registra su aviso. La prueba anterior se conserva en **Incidencia de la app** para ejecutarla expresamente. El [ejemplo anterior importable](../experiments/intent-lab/examples/app-context-workflow.json) sigue compatible, pero no sustituye al flujo maestro común.

La evidencia tiene procedencia `controlled_lab_probe`. No son registros de clientes ni logs de producción. La notificación **sí se persiste en el LAB**, con clave de idempotencia incidencia + flujo + bloque. No envía correo, crea ticket externo ni agenda especialista. Se puede añadir clasificación y contexto al recorrido respetando sus requisitos, pero conectar el recolector a logs autenticados del banco es otra integración.

## Conversación, trazas y persistencia

Una conversación nueva recibe hasta diez mensajes de contexto inicial. La continuación por preguntas conserva el contrato, el grafo y los resultados, con hasta diez respuestas adicionales y treinta mensajes totales. Al agotar ese límite con datos faltantes, propone atención humana y termina; no inventa los datos. **Nueva conversación** reinicia la evaluación.

La traza incluye copia y revisión del grafo, hash, idioma, clasificación inicial y específica, contrato, citas, condiciones, incidencia, aviso y tiempo por bloque. Las visitas repetidas al Contexto tienen índice y turno propios. La latencia suma procesamiento activo: no incluye el tiempo que la persona tarda en contestar ni equivale al tiempo de resolución bancaria. **Exportar JSON** descarga el resultado; mensajes y trazas permanecen locales.

Cada bloque guarda sus entradas antes de ejecutarse, incluyendo contexto, mensajes, turno y posición de la traza. Al repetirlo, `replayed_from` enlaza la ejecución original; los pasos previos llevan `reused: true`. `latency_ms` suma únicamente el procesamiento nuevo; `reused_latency_ms` informa por separado el tiempo histórico de los pasos reutilizados. Una ejecución creada antes de esta mejora puede continuarse y consultarse; sólo podrá repetir bloques que ya tengan entradas guardadas.

El progreso usa `POST /editor/workflows/{uuid}/run-stream` bajo `/lab-api`, con `mode: step | full`, eventos `execution_created`, `node_started`, `node_finished`, `edge_taken` y `paused`, `waiting_reply` o `complete`. `GET /editor/executions/{uuid}` recupera el checkpoint sin ejecutar. `POST /editor/executions/{uuid}/advance` exige la versión del checkpoint, el siguiente bloque correcto y, cuando espera, una respuesta. Versiones antiguas, ramas forzadas y concurrencia se rechazan antes de ejecutar. El endpoint `/run` sigue disponible.

`POST /editor/executions/{uuid}/replay`, con `version` y `node_id`, repite exactamente un bloque que tenga entradas guardadas. Comprueba versión, estado, reglas y concurrencia; no admite saltar a bloques no recorridos. Una solicitud repetida sobre la misma versión/bloque devuelve el ID ya creado (`409 replay_exists`), que la interfaz consulta sin repetir llamadas. El operador debe pulsar ▶ otra vez sobre la ejecución vigente para una nueva repetición voluntaria.

Una desconexión del navegador no cancela trabajo ya iniciado: termina la ejecución acotada y persiste su estado. Una interrupción del proceso deja el checkpoint interrumpido; nunca se reintenta una llamada o aviso silenciosamente. `POST /editor/master-workflow` crea el flujo predeterminado una sola vez y luego recupera ese mismo borrador con sus ediciones. Las plantillas anteriores intactas se actualizan al bloque inicial combinado y las seis ramas visibles conservando su ID y una copia en `workflow-revisions`; si ya tenía ediciones, se conserva. Al recuperar una ejecución de otra revisión se comparan las reglas: las diferencias visuales permiten continuar; las diferencias funcionales muestran el aviso de restauración y mantienen los resultados consultables. Consultar categorías y plantillas no consume modelos; todas las categorías comparten la misma plantilla.

| Archivo local privado | Contenido |
| --- | --- |
| `.local/intent-lab/master-workflow.json` | Identificador del único flujo compartido predeterminado. |
| `.local/intent-lab/workflow-executions/{uuid}.json` | Checkpoint, conversación, entradas por bloque, siguiente paso, clasificación, contrato y vínculo con la ejecución anterior. |
| `.local/intent-lab/workflows/{uuid}.json` | Última revisión del borrador, nodos, conexiones y validación. |
| `.local/intent-lab/runs/{uuid}.json` | Ejecución y snapshot de la revisión usada; editar el flujo no cambia este registro. |
| `.local/intent-lab/app-incidents/{uuid}.json` | Comprobación, referencia y logs controlados. |
| `.local/intent-lab/app-notifications.json` | Bandeja local y claves para evitar duplicados. |

Los datos anteriores están excluidos de Git. Sólo la preferencia de idioma usa localStorage. La implementación está diseñada para un operador local y un proceso FastAPI; no incorpora administración multiusuario ni publicación de flujos de producción.

Las citas siguen siendo **datos declarados**, no evidencia bancaria verificada. Los bloques de respuesta no bloquean tarjetas ni abonan devoluciones. El [evaluador bancario de evidencia y escalamiento](flujo-evidencia-y-escalamiento.md) conserva ese alcance separado. Voz, micrófono y llamadas quedan aplazados.

## Ejecutar las comprobaciones

Prepara y arranca el LAB según su [README](../experiments/intent-lab/README.md), luego:

```powershell
npm run build:lab
$env:PYTHONPATH = "$PWD/experiments/intent-lab"
.local/intent-lab-venv/Scripts/python.exe -m pytest experiments/intent-lab/tests -q
npm run test:lab:editor
npm run test:lab:steps
npm run test:lab:master
npm run test:lab:flows
```

`test:lab:editor` necesita el servidor en `127.0.0.1:5190` sirviendo la compilación nueva y Edge disponible. Crea o reutiliza tres flujos identificados como Verificación; crea incidencias y avisos locales. Comprueba Inicio/Play, nueve ejecuciones, ramas coloreadas, inserción con +, arrastre de tarjetas, conexión por puntos, movimiento, deshacer/rehacer, persistencia, exportación, casos/procedimientos, ES/EN/PT, móvil y accesibilidad. Bloquea ejecuciones de flujos que incluyan modelos; no consume las claves. Los artefactos quedan en `.local/intent-lab/verification/`.

`test:lab:flows` conserva las pruebas del [visor de recorridos anterior](lab-flujos-react-flow.md), accesible como **Evaluaciones anteriores**. Los tests Python comprueban que los eventos corresponden a la ruta ejecutada, que el inicio se emite antes de recibir el modelo y que se conserva el bloqueo y la revisión ante errores.

`test:lab:steps` comprueba guardado automático desde un borrador editado, ▶ por bloque y salida, rama contraria deshabilitada, recarga sin repetición, continuación completa y errores de conexiones. Ejecuta doce avances locales en ES/EN/PT, sin modelos, y revisa escritorio/móvil con axe. Python cubre las seis selecciones dinámicas de contrato, consultas, límites, revisión, concurrencia y retornos con respuestas hasta completar el contexto.

`test:lab:master` inicia un servidor aislado en **5191**, que debe estar libre. Usa el mismo motor FastAPI y frontend compilado, con respuestas de proveedores controladas y registros identificados de verificación. No usa las claves ni altera los flujos del operador en 5190. Repite tres conversaciones en ES/EN/PT: cargo con datos faltantes y continuación, fallo de app con logs/aviso propuestos, y solicitud de atención humana. Verifica la ruta, la función propuesta, ausencia de operaciones/avisos, recuperación sin repetir clasificación y accesibilidad escritorio/móvil. También comprueba clics, un movimiento mínimo del puntero, guardado/recarga durante una pausa, catálogo de 24 categorías, cambio/restauración de reglas y repetición explícita de Jev sin recalcular pasos previos. Los resultados son una prueba funcional; no miden calidad de Jev/Luna. Puede usarse `NEXQORI_LAB_PYTHON` para indicar el intérprete y `PLAYWRIGHT_CHANNEL` para otro navegador instalado.
