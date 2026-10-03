# Base de llamada con GPT-Live

Estado al 3 de octubre de 2026, America/Lima: implementación para pruebas posteriores. La voz permanece desactivada en Compose normal. No se ha probado una llamada real ni el acceso de la cuenta a `gpt-live-1`. No se ha usado el micrófono ni consumido crédito de voz durante el desarrollo.

## Recorrido

1. El cliente abre Iniciar llamada y elige una voz. El navegador comprueba que la función está habilitada antes de pedir permiso para el micrófono.
2. FastAPI comprueba sesión, titular de la conversación y referencias seleccionadas. Crea una sesión GPT-Live por WebRTC y abre un canal de control del servidor (*sideband*). La clave queda en el servidor.
3. GPT-Live envía fragmentos de transcripción y delegaciones por el canal del servidor. El adaptador agrupa los fragmentos anteriores a la delegación y llama a `run_chat_turn`, el mismo servicio que usa `/api/assistant/flow`.
4. Jev, el contrato y LangGraph conservan el estado de la conversación. Cada delegación usa una clave de idempotencia estable. Los resultados se guardan en PostgreSQL y aparecen en el chat.
5. La voz recibe sólo mensajes generales y preguntas de una lista fija. Importes, saldos, referencias y resultados bancarios se muestran en pantalla. No se reenvían las respuestas bancarias completas a GPT-Live.
6. El cliente puede silenciar o terminar. El cierre solicita `session.close`; el servidor registra si recibe `session.closed`. Logout, pérdida del navegador y límite de cinco minutos también provocan cierre. Silenciar no termina la sesión ni su facturación.

La confirmación de reclamos, pagos, transferencias, bloqueo y devoluciones sigue en sus pantallas existentes. Ninguna función de voz ejecuta esas operaciones. La voz no dispone de SQL, identificadores de otros usuarios, contraseñas ni herramientas financieras libres. El navegador sólo puede enviar `session.close` al canal de OpenAI; no puede configurar prompts ni enviar resultados de herramientas.

## Qué está construido

Durante la llamada, los resultados aparecen en el chat. Para cambiar el movimiento, seleccionar otro caso, preparar un PDF o confirmar una gestión, terminar primero la llamada. La conversación permanece disponible. Esta primera implementación evita cambios simultáneos de contexto entre los controles y la voz.

| Parte | Implementación |
|---|---|
| Inicio y configuración | `GET /api/voice/capabilities`, `POST /api/voice/sessions`; voz elegida al iniciar, ES/EN/PT |
| Continuidad | `backend/workflow_chat.py:run_chat_turn`, conversación y contrato compartidos con texto |
| Lecturas y preguntas | Gateway existente del banco; sólo referencias del titular; resultados con auditoría |
| Recuperación del resultado | `POST /api/voice/sessions/{id}/heartbeat`, sólo la sesión bancaria original |
| Cierre | `POST /api/voice/sessions/{id}/close`, controles del navegador y del servidor |
| Persistencia | `voice_sessions`; delegaciones, último resultado, revisión, duración observada y uso final si llega |
| Recuperación | Botón para cerrar una llamada anterior; al arrancar con voz habilitada se intenta cerrar sesiones activas anteriores |
| Interfaz | Voz, silencio, terminar, subtítulos recientes, respuesta bancaria en el chat y regreso a texto |

No se guarda audio local ni se solicita grabación para futuras bifurcaciones (`store: false`). Los fragmentos son temporales; los turnos atendidos permanecen en el historial bancario. La salida hablada exacta sólo aparece como subtítulos temporales; la auditoría conserva el resultado verificado del banco, no una grabación certificada de lo que el modelo dijo.

## Probar sin voz ni proveedores externos

```powershell
.venv-app/Scripts/python.exe -m pytest backend/tests/test_voice.py -q
npm test
npm run test:voice:ui
npm run test:chat:flow
```

Las pruebas de API sustituyen OpenAI/Jev/LLM por proveedores falsos. La prueba de interfaz levanta una base SQLite aislada en `127.0.0.1:5192` y sustituye WebRTC, micrófono y transporte. Comprueba ES/EN/PT, cierre, silencio, bloqueo del compositor durante la llamada y resultados visibles. No usa los usuarios manuales del banco. El puerto 5192 debe estar libre.

## Activación posterior, cuando se decida probar una llamada real

Comprobación del 3 de octubre: la clave configurada respondió correctamente al catálogo, pero `gpt-live-1` devolvió 404 y no aparecieron modelos de voz accesibles. La base se integró con las mejoras actuales del chat; se conserva la llamada desactivada mientras se resuelve el acceso. No se inició una sesión facturada ni se usó el micrófono.

Antes de habilitar el Compose de voz, ejecutar `node scripts/check-voice-access.mjs`. Sólo consulta el modelo desde el contenedor, conserva la clave en servidor y devuelve código de salida 1 si no confirma acceso. Un resultado correcto acredita acceso al modelo, no una llamada de audio validada. Después deben probarse WebRTC, voz y cierre.

1. Conservar un respaldo de PostgreSQL. La migración `f492b731e845` sólo añade la tabla de sesiones de voz; no cambia saldos, pagos ni conversaciones existentes.
2. Configurar `OPENAI_LIVE_API_KEY` en `.local/intent-lab/providers.env`, o reutilizar `LLM_API_KEY` ya presente en ese archivo. No poner claves en React ni Git. El proyecto de OpenAI debe tener acceso y facturación para `gpt-live-1`; no se comprobó esa disponibilidad.
3. Ejecutar el Compose adicional, que habilita la función y permite el micrófono para el mismo origen:

```powershell
docker compose -f compose.yaml -f compose.voice.yaml up --build -d api web
```

4. Iniciar sesión en el banco y abrir Iniciar llamada. Se requiere localhost o HTTPS y permiso del micrófono. Empezar con una conversación de prueba; máximo cinco minutos. La creación no se reintenta automáticamente si su resultado es incierto.
5. Probar consulta de movimientos, cobro excesivo con aclaración de importe y pago pendiente. Interrumpir, silenciar, terminar y volver al chat. Comprobar que no hay operaciones financieras nuevas sin confirmación en pantalla.

Para volver a desactivar, terminar las llamadas abiertas y recrear con Compose normal:

```powershell
docker compose -f compose.yaml up --build -d api web
```

## Límites que quedan por evaluar en la prueba real

- Compatibilidad del protocolo, negociación WebRTC, permiso del proyecto, latencia, voz/acento e interrupciones no se han validado con OpenAI. El adaptador sigue la documentación oficial consultada en la fecha indicada.
- El anfitrión está diseñado para un proceso API, como el Compose local actual. Un despliegue con varios workers requiere coordinación distribuida y reservas globales de llamadas. No ofrece alta disponibilidad.
- Se agrupan transcripciones por marcas de tiempo de las delegaciones con una breve espera de recepción. GPT-Live no entrega un turno completo de texto. Fragmentos tardíos, correcciones y ruido deben evaluarse con audio real; nunca equivalen a autorización bancaria.
- Una respuesta bancaria en curso puede acabar después de colgar y queda en el historial. No se vuelve a abrir una llamada ni se ejecuta una operación por ello. Si no aparece aún, recuperar la conversación desde Conversaciones.
- La conexión de voz y los subtítulos no son prueba de que el cliente escuchó toda la respuesta.
- Si falla el cierre, queda marcado como no confirmado y se permite volver a intentarlo. Si se pierde la respuesta de creación antes de conocer el ID del proveedor, no es posible garantizar el cierre desde ese ID; no se reintenta la creación con la misma clave. Revisar el consumo del proveedor antes de repetir pruebas con fallos de red.
- El cierre por abandono usa una señal del navegador y un plazo de 45 segundos. Hay un límite de cinco minutos y 40 delegaciones por llamada. No se promete un tope exacto de facturación ante fallos del proveedor o del servidor.
- El estilo inicial es cálido y breve según el idioma. No se añadió clonación de voz ni se probó un acento regional específico.

Fuentes oficiales: [GPT-Live](https://developers.openai.com/api/docs/guides/live), [WebRTC](https://developers.openai.com/api/docs/guides/voice-webrtc), [delegación](https://developers.openai.com/api/docs/guides/live-delegation), [control del servidor](https://developers.openai.com/api/docs/guides/voice-server-controls), [sesiones](https://developers.openai.com/api/docs/guides/live-conversations), [creación](https://developers.openai.com/api/reference/resources/live/methods/create).
