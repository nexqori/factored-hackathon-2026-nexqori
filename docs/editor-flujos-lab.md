# Flujos de atención: casos, preguntas y acciones

Abre [Flujos de atención](http://localhost:5190/?view=flows&mode=editor&lang=es). El lienzo ocupa la pantalla; los casos y bloques están a la izquierda y la configuración aparece a la derecha al seleccionar un paso. FastAPI valida e interpreta **el grafo guardado**. Cambiar una conexión cambia la ruta que se ejecuta.

## Empezar con un problema

1. En **Casos**, elige un problema. Se abre su flujo, con Inicio seleccionado, una pregunta editable y su conversación previa cuando existe un escenario conversacional.
2. En Inicio, abre **Procedimiento del caso** para ver los pasos del contrato y los datos necesarios. Escribe la pregunta del cliente; **Nueva conversación** permite empezar sin el contexto del ejemplo.
3. Pulsa **Guardar borrador**, después **Probar flujo** en Inicio o en la barra superior. El guardado comprueba las conexiones; no hace falta validar dos veces. Si cambias el flujo, vuelve a guardarlo antes de ejecutar.
4. El bloque en ejecución muestra un indicador y la vista sigue su posición. El servidor envía cada inicio, final y conexión tomada mientras procesa el turno. Las ramas **Sí** recorridas se ven verdes y las **No**, ocres; lo no recorrido permanece gris. Los pasos rápidos pueden terminar entre dos actualizaciones de pantalla: la traza conserva todos, sin ralentización artificial.
5. En **Ejecución** verás el caso identificado por Jev, la respuesta, **Acciones y pasos realizados**, condiciones Sí/No y tiempos. Pulsa un paso para ver su salida. **Acciones por revisar en el banco** muestra propuestas pendientes de evidencia, permisos y confirmación; no las presenta como realizadas.
6. Vuelve a Inicio o abre **Conversación de prueba** para responder a la pregunta siguiente. El turno conserva la conversación y vuelve a evaluar el flujo desde Inicio.

### Casos disponibles y procedencia

| Problema | Procedencia | Procedimiento inicial |
| --- | --- | --- |
| Cargo no reconocido | 12.297 reclamos | Identificar movimiento, contrastar datos, revisar protección y posible devolución. |
| Cobro incorrecto | 12.194 reclamos | Recoger importe/fecha, contrastar cargo y revisar devolución. |
| Pago pendiente o rechazado | Alcance acordado, sin frecuencia directa de reclamos | Identificar intento y estado antes de proponer otro pago. |
| Problema con la app | 12.128 reclamos | Recoger síntoma/intentos y, en el recorrido local, logs de incidencia y aviso. |
| Atención en sucursal | 11.892 reclamos | Recoger visita y motivo, preparar revisión de atención. |
| Experiencia de atención | 11.886 reclamos | Registrar contexto de atención y preparar seguimiento. |

Los conteos proceden de [evidence.json](../experiments/intent-lab/evidence.json), sobre 67.095 reclamos; son registros, no clientes únicos. Los seis contratos vienen del [catálogo de procedimientos](../backend/workflow_catalog.json). **Consultas y otros alcances** contiene las 18 categorías restantes: 24 en total. El buscador filtra casos y bloques. Elegir un caso no fuerza la clasificación: Jev decide según los mensajes enviados.

Los cinco escenarios conversacionales son ejemplos redactados basados en las categorías. Las demás categorías incluyen una pregunta inicial. El procedimiento indica esta procedencia; no se presentan como transcripciones auténticas. Sólo el flujo de problema de la app incorpora por defecto la rama de logs locales; las demás plantillas preparan contexto y preguntas según su contrato.

## Crear y ajustar un flujo

1. Abre **Mis flujos** con la carpeta de la barra superior. Puedes recuperar un flujo o crear uno desde cero, con Plantilla bancaria o con Incidencia de la app.
2. Usa el **+** del lienzo para abrir Bloques y arrastra una tarjeta a un espacio libre. El **+ de una conexión** inserta un bloque entre dos pasos, conservando la continuación; el **+ de una salida libre** conecta el paso nuevo. También puedes arrastrar una salida al espacio vacío para elegir el siguiente bloque.
3. Haz clic en un bloque para editarlo en el panel derecho. Une sus puntos o arrastra el extremo de una conexión para cambiar el destino. También puedes elegir el destino en **Conexiones de salida**, útil con teclado y en móvil. Tab/Enter selecciona los bloques y abre su configuración.
4. Las condiciones tienen salidas **Sí** y **No**. Conecta ambas. Insertar una condición conserva la continuación por Sí y deja No pendiente de conectar. Un bloque terminal (Pregunta, Respuesta o Revisión humana) se añade al lienzo o a una salida libre; no se inserta sobre una conexión existente porque cortaría su continuación. **Deshacer/Rehacer** recupera ediciones y movimientos; **Ordenar bloques** distribuye el grafo por niveles.
5. **Validar conexiones** indica el bloque que falta conectar o el requisito que falta en esa ruta. Se pueden guardar borradores incompletos; no se pueden ejecutar hasta corregirlos. Elimina los bloques que sobren desde su panel.
6. **Guardar borrador** crea una revisión y actualiza el enlace del navegador para recuperar ese flujo. Cambia Español / English / Português para editar el texto de ese idioma; cambiar de idioma conserva el borrador abierto.

**Duplicar** crea una variante pendiente de guardar. **Exportar JSON** descarga la definición completa para compartirla; **Importar JSON** la valida y abre como otro borrador. Revisa el contexto antes de compartir: puede contener lo que hayas escrito. Las claves se configuran únicamente en el archivo privado de proveedores.

El guardado utiliza revisión optimista. Si otro editor guardó antes, recarga el flujo y vuelve a aplicar los cambios. La biblioteca tiene un máximo de 50 flujos locales. Los flujos son acíclicos, tienen un solo Inicio, hasta 24 bloques y 36 conexiones. Cada salida admite un destino; se permiten varias entradas al mismo bloque. Cada ruta debe haber pasado por sus requisitos: por ejemplo, Contexto según el caso necesita Jev, y Aviso local necesita Recoger logs.

## Bloques disponibles

| Bloque | Configuración y efecto |
| --- | --- |
| Inicio | Recibe mensajes e idioma del turno. |
| Clasificación Jev | Clasifica entre las 24 categorías existentes; instrucciones adicionales por idioma. Máximo uno por flujo. |
| Contexto · Luna | Elige campos según Jev o una lista explícita. Admite instrucciones y referencia no verificada. Extrae citas exactas de mensajes del cliente. Máximo uno. |
| Condición | Compara intención, familia, datos faltantes, necesidad de atención humana o error registrado en los logs. |
| Pregunta | Termina el turno con hasta dos preguntas sobre datos faltantes o una pregunta personalizada. |
| Respuesta | Termina con información o propuesta de revisar en el banco. Texto por idioma. |
| Revisión humana | Propone la intervención de una persona y termina el turno. No contacta a nadie. |
| Recoger logs | Lee la incidencia local vinculada a la comprobación de acceso. Máximo uno. |
| Aviso local | Registra una notificación en Avisos de incidencias, con referencia correlacionada. |

No se aceptan bloques de código, SQL, URLs de ejecución, claves ni herramientas bancarias. Los modelos se llaman sólo si la ruta pasa por su bloque: a lo sumo una llamada a Jev y una a Luna por turno. Abrir, mover, validar, guardar e importar no llama a proveedores. No hay reintentos automáticos. Un error del proveedor detiene la ruta y queda en la traza.

## Probar el error de acceso, sin consumir modelos

1. Crea un flujo con **Incidencia de la app** y guarda.
2. Haz clic en **Inicio** y pulsa **Reproducir error de acceso**. El servidor ejecuta una comprobación controlada que lanza y captura un fallo de carga de sesión. Crea un ID y una referencia `APP-…`.
3. Pulsa **Probar flujo**. El recorrido será Inicio → Recoger logs → ¿Se confirmó el error? → Aviso local → Confirmar el aviso.
4. Selecciona Recoger logs en la traza: verás inicio de comprobación, error `session_load_timeout`, marca de tiempo y referencia común. El código 503 forma parte del registro de prueba; no es una caída del servidor bancario. `timeout_budget_ms` es el presupuesto configurado del caso, no latencia medida.
5. Abre **Avisos de incidencias** abajo. La referencia coincide con la de los logs. Repite un turno con la misma incidencia: se conserva el aviso existente, sin duplicarlo. Una nueva comprobación crea otra incidencia.

Esta plantilla no tiene bloques de modelos y funciona sin API keys. Si ejecutas sin vincular una incidencia, se detiene pidiendo la comprobación. No infiere la existencia de logs a partir de lo que diga el cliente. La rama No está preparada para un registro sin fallo; el botón actual produce siempre el fallo controlado.

Para combinarlo con IA, importa [app-context-workflow.json](../experiments/intent-lab/examples/app-context-workflow.json). Jev identifica el caso; sólo la rama de problema de la app recoge la incidencia y registra el aviso. Después, Luna recibe el contexto y la evidencia local con su procedencia; el recorrido pregunta por lo que falta o propone revisión. Reproduce el error antes de pulsar Probar flujo. Esta variante sí utiliza los proveedores configurados. El ejemplo contiene definiciones y textos, sin conversaciones ni credenciales.

La evidencia tiene procedencia `controlled_lab_probe`. No son registros de clientes ni logs de producción. La notificación **sí se persiste en el LAB**, con clave de idempotencia incidencia + flujo + bloque. No envía correo, crea ticket externo ni agenda especialista. Se puede añadir clasificación y contexto al recorrido respetando sus requisitos, pero conectar el recolector a logs autenticados del banco es otra integración.

## Conversación, trazas y persistencia

Cada nuevo turno recorre el flujo desde Inicio con los mensajes visibles. Una pregunta termina ese turno; la respuesta del cliente aporta contexto al siguiente. Máximo diez mensajes enviados, incluyendo respuestas previas. Usa Nueva conversación para reiniciar. Guardar un borrador no publica reglas al banco.

La traza incluye copia del grafo y revisión, hash de la definición y prompt de extracción, idioma, clasificación, citas, condiciones tomadas, incidencia, aviso y tiempo por bloque. El tiempo es latencia de evaluación, no tiempo de resolución bancaria. **Exportar JSON** bajo la traza descarga ese resultado. El registro completo, que además contiene los mensajes de entrada, queda disponible en `GET /lab-api/runs/{uuid}`. Recargar un flujo recupera su definición; no reabre automáticamente la conversación ni vuelve a ejecutar.

El progreso usa `POST /lab-api/editor/workflows/{uuid}/run-stream` con eventos NDJSON del intérprete, incluida la respuesta completa persistida al terminar. Una desconexión del navegador no cancela el trabajo ya iniciado: termina dentro del límite del grafo y libera el bloqueo del proveedor. No se reintenta automáticamente. El endpoint anterior `/run` sigue disponible. Casos y plantillas se consultan sin modelos mediante `/editor/cases?language=es` y `/editor/case-template/{intent}`.

| Archivo local privado | Contenido |
| --- | --- |
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
npm run test:lab:flows
```

`test:lab:editor` necesita el servidor en `127.0.0.1:5190` sirviendo la compilación nueva y Edge disponible. Crea o reutiliza tres flujos identificados como Verificación; crea incidencias y avisos locales. Comprueba Inicio/Play, nueve ejecuciones, ramas coloreadas, inserción con +, arrastre de tarjetas, conexión por puntos, movimiento, deshacer/rehacer, persistencia, exportación, casos/procedimientos, ES/EN/PT, móvil y accesibilidad. Bloquea ejecuciones de flujos que incluyan modelos; no consume las claves. Los artefactos quedan en `.local/intent-lab/verification/`.

`test:lab:flows` conserva las pruebas del [visor de recorridos anterior](lab-flujos-react-flow.md), accesible como **Evaluaciones anteriores**. Los tests Python comprueban que los eventos corresponden a la ruta ejecutada, que el inicio se emite antes de recibir el modelo y que se conserva el bloqueo y la revisión ante errores.
