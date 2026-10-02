# Editor de flujos y comprobación de incidencias

Abre el [editor local](http://localhost:5190/?view=flows&mode=editor&lang=es). Permite crear, duplicar, conectar y configurar recorridos de Nexqori. React Flow dibuja los bloques; FastAPI valida e interpreta **el grafo guardado**. Cambiar una conexión cambia la ruta que se ejecuta.

## Crear y ajustar un flujo

1. En **Nuevo flujo**, elige Plantilla bancaria o Incidencia de la app y pulsa Nuevo flujo. **Mis flujos** recupera los borradores del servidor local.
2. Pulsa o arrastra un bloque de la biblioteca. Selecciónalo para editar su nombre, instrucciones, contexto o condición. Une sus puntos de salida y entrada; también puedes elegir el destino en **Conexiones de salida**, útil con teclado y en móvil.
3. Las condiciones tienen salidas **Sí** y **No**. Conecta ambas. Elimina los bloques que ya no formen parte del recorrido con **Eliminar bloque**.
4. Usa **Validar conexiones**. Los errores indican el bloque que falta conectar o el requisito que falta en esa ruta. Se pueden guardar borradores incompletos; no se pueden ejecutar hasta corregirlos.
5. **Guardar borrador** crea una revisión. Escribe el mensaje y pulsa **Probar flujo**. Se iluminan los bloques recorridos y aparecen la respuesta, tiempos y salida de cada paso.
6. Cambia Español / English / Português para editar el texto de ese idioma. Los nombres y respuestas personalizadas tienen cobertura en los tres idiomas; cambiar de idioma conserva el borrador abierto.

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
| Aviso local | Registra una notificación en la bandeja del LAB, con referencia de incidencia. |

No se aceptan bloques de código, SQL, URLs de ejecución, claves ni herramientas bancarias. Los modelos se llaman sólo si la ruta pasa por su bloque: a lo sumo una llamada a Jev y una a Luna por turno. Abrir, mover, validar, guardar e importar no llama a proveedores. No hay reintentos automáticos. Un error del proveedor detiene la ruta y queda en la traza.

## Probar el error de acceso, sin consumir modelos

1. Crea un flujo con **Incidencia de la app** y guarda.
2. En **Comprobación de acceso a la app**, pulsa **Reproducir error de acceso**. El servidor ejecuta una comprobación controlada que lanza y captura un fallo de carga de sesión. Crea un ID y una referencia `APP-…`.
3. Pulsa **Probar flujo**. El recorrido será Inicio → Recoger logs → ¿Se confirmó el error? → Aviso local → Confirmar el aviso.
4. Selecciona Recoger logs en la traza: verás inicio de comprobación, error `session_load_timeout`, marca de tiempo y referencia común. El código 503 forma parte del registro de prueba; no es una caída del servidor bancario. `timeout_budget_ms` es el presupuesto configurado del caso, no latencia medida.
5. Abre **Avisos del LAB**. La referencia coincide con la de los logs. Repite un turno con la misma incidencia: se conserva el aviso existente, sin duplicarlo. Una nueva comprobación crea otra incidencia.

Esta plantilla no tiene bloques de modelos y funciona sin API keys. Si ejecutas sin vincular una incidencia, se detiene pidiendo la comprobación. No infiere la existencia de logs a partir de lo que diga el cliente. La rama No está preparada para un registro sin fallo; el botón actual produce siempre el fallo controlado.

Para combinarlo con IA, importa [app-context-workflow.json](../experiments/intent-lab/examples/app-context-workflow.json). Jev identifica el caso; sólo la rama de problema de la app recoge la incidencia y registra el aviso. Después, Luna recibe el contexto y la evidencia local con su procedencia; el recorrido pregunta por lo que falta o propone revisión. Reproduce el error antes de pulsar Probar flujo. Esta variante sí utiliza los proveedores configurados. El ejemplo contiene definiciones y textos, sin conversaciones ni credenciales.

La evidencia tiene procedencia `controlled_lab_probe`. No son registros de clientes ni logs de producción. La notificación **sí se persiste en el LAB**, con clave de idempotencia incidencia + flujo + bloque. No envía correo, crea ticket externo ni agenda especialista. Se puede añadir clasificación y contexto al recorrido respetando sus requisitos, pero conectar el recolector a logs autenticados del banco es otra integración.

## Conversación, trazas y persistencia

Cada nuevo turno recorre el flujo desde Inicio con los mensajes visibles. Una pregunta termina ese turno; la respuesta del cliente aporta contexto al siguiente. Máximo diez mensajes enviados, incluyendo respuestas previas. Usa Nueva conversación para reiniciar. Guardar un borrador no publica reglas al banco.

La traza incluye copia del grafo y revisión, hash de la definición y prompt de extracción, idioma, clasificación, citas, condiciones tomadas, incidencia, aviso y tiempo por bloque. El tiempo es latencia de evaluación, no tiempo de resolución bancaria. **Exportar JSON** bajo la traza descarga ese resultado. El registro completo, que además contiene los mensajes de entrada, queda disponible en `GET /lab-api/runs/{uuid}`. Recargar un flujo recupera su definición; no reabre automáticamente la conversación ni vuelve a ejecutar.

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

`test:lab:editor` necesita el LAB en `127.0.0.1:5190` sirviendo la compilación nueva y Edge disponible. Crea o reutiliza tres flujos identificados como Verificación; crea incidencias y avisos locales. Comprueba conexiones editadas, persistencia, ejecución, ausencia de duplicados, exportación, ES/EN/PT, móvil y accesibilidad. Bloquea ejecuciones de flujos que incluyan modelos; no consume las claves. Los artefactos quedan en `.local/intent-lab/verification/`.

`test:lab:flows` conserva las pruebas del [visor de recorridos anterior](lab-flujos-react-flow.md), accesible como **Recorridos anteriores**.
