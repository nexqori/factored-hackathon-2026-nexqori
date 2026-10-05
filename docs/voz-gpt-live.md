# Base de llamada con GPT-Live

Estado al 4 de octubre de 2026, America/Lima: acceso a `gpt-live-1` confirmado con HTTP 200 después de permitirlo en el proyecto OpenAI. El usuario realizó una llamada: PostgreSQL conserva cuatro delegaciones y el cierre remoto confirmado. No hay una grabación ni una transcripción hablada completa para evaluar pronunciación o calidad del audio. Se corrigieron los problemas observados en búsqueda y navegación; falta repetir ese recorrido con audio real tras el despliegue. Compose normal conserva la voz apagada, por lo que los siguientes arranques deben incluir `compose.voice.yaml` para mantenerla habilitada.

## Recorrido

El asistente se llama **Nexi**; **Nexqori** es la marca del banco. El chat, las etiquetas accesibles y las instrucciones iniciales de llamada usan Nexi en ES/EN/PT. Los perfiles Marin, Cedar, Coral, Bossa y Tempo conservan la misma identidad del asistente. Una llamada que ya empezó conserva sus instrucciones iniciales hasta terminar.

1. El cliente abre Iniciar llamada dentro del panel del asistente y elige una voz. La vista de llamada ocupa ese panel; el historial y el borrador de texto se conservan al volver. El navegador comprueba que la función está habilitada antes de pedir permiso para el micrófono.
2. FastAPI comprueba sesión, titular de la conversación y referencias seleccionadas. Crea una sesión GPT-Live por WebRTC y abre un canal de control del servidor (*sideband*). La clave queda en el servidor.
3. GPT-Live envía fragmentos de transcripción y delegaciones por el canal del servidor. El adaptador agrupa los fragmentos anteriores a la delegación y llama a `run_chat_turn`, el mismo servicio que usa `/api/assistant/flow`.
4. Jev, el contrato y LangGraph conservan el estado de la conversación. Cada delegación usa una clave de idempotencia estable. Los resultados se guardan en PostgreSQL y aparecen en el chat.
5. La voz recibe sólo mensajes generales y preguntas de una lista fija. Importes, saldos, referencias y resultados bancarios se muestran en pantalla. No se reenvían las respuestas bancarias completas a GPT-Live.
6. El cliente puede silenciar o terminar. El cierre solicita `session.close`; el servidor registra si recibe `session.closed`. Logout, pérdida del navegador y límite de cinco minutos también provocan cierre. Silenciar no termina la sesión ni su facturación.

La confirmación de reclamos, pagos, transferencias, bloqueo y devoluciones sigue en sus pantallas existentes. Ninguna función de voz ejecuta esas operaciones. La voz no dispone de SQL, identificadores de otros usuarios, contraseñas ni herramientas financieras libres. El navegador sólo puede enviar `session.close` al canal de OpenAI; no puede configurar prompts ni enviar resultados de herramientas.

## Qué está construido

Durante la llamada, el panel muestra al agente arriba y la transcripción debajo, con «Lo que entendí» y «Respuesta del agente». Sólo esa área de texto se desplaza; el agente y los controles Silenciar y Terminar llamada permanecen visibles. El panel limita su altura al espacio de la ventana, también en móvil. Cada resultado bancario nuevo se abre sobre los subtítulos, en «Ver resultado de tu consulta», y puede contraerse. La llamada puede abrir Movimientos con filtros y proponer un registro; una confirmación verbal breve selecciona esa referencia para investigar. No confirma una operación. Los formularios de PDF y confirmación de gestiones permanecen en el chat escrito al terminar la llamada, conservando conversación y borrador.

### Búsqueda proactiva y reglas del agente

- El rol inicial identifica un agente virtual de atención bancaria. Delega al banco las consultas, problemas y peticiones de navegación; solicita sólo una pista útil cuando hace falta y conserva las anteriores.
- La búsqueda autenticada combina servicio, estado, fecha, importe cobrado y referencia. El importe del plan no sustituye al cobro. Los filtros se aplican antes del límite de 20 resultados y sólo sobre el titular autenticado. No hay búsqueda aproximada de importes.
- Una transacción fallida no se sustituye por otra completada. Sin coincidencia, abre la búsqueda y pide una pista o permite mostrar todos los movimientos. La propuesta muestra fecha, importe y referencia para que el cliente la confirme.
- «Muéstrame las últimas transacciones» abre Movimientos y conserva contrato, observaciones y presupuesto de preguntas. Una petición de navegación con teléfono, estado o fecha aplica esos filtros a la lista sin registrarlos como evidencia ni alterar el relato del problema.
- Los registros completos permanecen en pantalla. A petición del usuario, GPT-Live recibe el resumen numérico mínimo definido al final de esta guía: importe/fecha/estado, comparación agregada y número de expediente del titular. No recibe logs ni historiales completos.

Prueba manual del fallo observado: «Tengo un problema con una transacción fallida» → «Es la última del teléfono» → «Muéstrame las últimas transacciones» → indicar una referencia visible → confirmar «Sí, es este». Comprobar que la lista cambia, la llamada continúa y el problema conserva su contexto. Si el registro no existe, debe decirlo; no debe inventar ni ejecutar una devolución.

La animación responde al nivel del audio recibido y reproducido por el navegador. No se activa por recibir subtítulos ni por silenciar el micrófono del cliente; se detiene en silencio, al pausar o al cerrar. El análisis Web Audio es local, no captura otro micrófono ni almacena sonido. Si no está disponible, la llamada y los subtítulos siguen funcionando sin animación. Con movimiento reducido se conserva un indicador estático y el estado en texto. Esto describe la implementación y su prueba con transporte controlado; sigue pendiente validar audio real con el proveedor.

Marin es la voz inicial; el selector ofrece las voces permitidas por el servidor (Marin, Cedar, Coral, Bossa y Tempo). Se elige antes de iniciar: GPT-Live requiere una sesión nueva para cambiarla. El idioma sigue la selección ES/EN/PT y las instrucciones actuales piden un tono cálido y breve. No hay selector de acentos ni prueba de pronunciación regional. Los fragmentos recibidos se ordenan por sus tiempos del proveedor, conservando espacios y palabras repetidas; el panel mantiene hasta 400 fragmentos recientes en memoria y no los almacena en el navegador.

En la interfaz, el selector se presenta como **Agente** y muestra una descripción breve: Marin (atención bancaria), Cedar (pagos y movimientos), Coral (reclamos y seguimiento), Bossa (servicios y recibos) y Tempo (ayuda con la app). Son perfiles de presentación del mismo agente virtual y flujo compartido; elegir un nombre configura la voz, no añade modelos especializados, permisos ni derivaciones nuevas. Jev y los contratos siguen determinando la ruta por el caso. La información de IA, envío de audio y duración está disponible en «Sobre la llamada».

| Parte | Implementación |
|---|---|
| Inicio y configuración | `GET /api/voice/capabilities`, `POST /api/voice/sessions`; voz elegida al iniciar, ES/EN/PT |
| Continuidad | `backend/workflow_chat.py:run_chat_turn`, conversación y contrato compartidos con texto |
| Lecturas y preguntas | Gateway existente del banco; sólo referencias del titular; resultados con auditoría |
| Recuperación del resultado | `POST /api/voice/sessions/{id}/heartbeat`, sólo la sesión bancaria original |
| Cierre | `POST /api/voice/sessions/{id}/close`, controles del navegador y del servidor |
| Persistencia | `voice_sessions`; delegaciones, último resultado, revisión, duración observada y uso final si llega |
| Recuperación | Botón para cerrar una llamada anterior; al arrancar con voz habilitada se intenta cerrar sesiones activas anteriores |
| Interfaz | Vista exclusiva dentro del chatbot, voz elegible antes de iniciar, silencio, terminar, transcripción por hablante, botón de detalle y comparación, revisión confirmada del reclamo y regreso a texto conservando borrador |

No se guarda audio local ni se solicita grabación para futuras bifurcaciones (`store: false`). Los fragmentos son temporales; los turnos atendidos permanecen en el historial bancario. La salida hablada exacta sólo aparece como subtítulos temporales; la auditoría conserva el resultado verificado del banco, no una grabación certificada de lo que el modelo dijo.

## Probar sin voz ni proveedores externos

```powershell
.venv-app/Scripts/python.exe -m pytest backend/tests/test_voice.py -q
npm test
npm run test:voice:ui
npm run test:chat:flow
```

Las pruebas de API sustituyen OpenAI/Jev/LLM por proveedores falsos. La prueba de interfaz levanta una base SQLite aislada en `127.0.0.1:5192` y sustituye WebRTC, micrófono y transporte. Comprueba ES/EN/PT, elección de voz, transcripciones de ambos hablantes con fragmentos tardíos/duplicados, cierre, silencio, vista exclusiva de llamada, controles en móvil y conservación del borrador/resultado al regresar al chat. No usa los usuarios manuales del banco. El puerto 5192 debe estar libre.

## Activación posterior, cuando se decida probar una llamada real

Comprobación histórica del 3 de octubre: `gpt-live-1` devolvió 404. El 4 de octubre el usuario permitió el modelo en el proyecto y se confirmó acceso. La configuración estándar sigue apagada; el banco local usa el archivo adicional de voz.

Antes de habilitar el Compose de voz, ejecutar `node scripts/check-voice-access.mjs`. Sólo consulta el modelo desde el contenedor, conserva la clave en servidor y devuelve código de salida 1 si no confirma acceso. Un resultado correcto acredita acceso al modelo, no una llamada de audio validada. Después deben probarse WebRTC, voz y cierre.

1. Conservar un respaldo de PostgreSQL. La migración `f492b731e845` sólo añade la tabla de sesiones de voz; no cambia saldos, pagos ni conversaciones existentes.
2. Configurar `OPENAI_LIVE_API_KEY` en `.local/intent-lab/providers.env`, o reutilizar `LLM_API_KEY` ya presente en ese archivo. No poner claves en React ni Git. El proyecto de OpenAI debe tener acceso y facturación para `gpt-live-1`; comprobarlo para cada entorno.
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

- La llamada realizada acredita delegación y cierre remoto. Latencia, pronunciación, interrupciones y el nuevo recorrido proactivo necesitan revisión con audio real; las pruebas automatizadas sustituyen el transporte.
- El anfitrión está diseñado para un proceso API, como el Compose local actual. Un despliegue con varios workers requiere coordinación distribuida y reservas globales de llamadas. No ofrece alta disponibilidad.
- Se agrupan transcripciones por marcas de tiempo de las delegaciones con una breve espera de recepción. GPT-Live no entrega un turno completo de texto. Fragmentos tardíos, correcciones y ruido deben evaluarse con audio real; nunca equivalen a autorización bancaria.
- Una respuesta bancaria en curso puede acabar después de colgar y queda en el historial. No se vuelve a abrir una llamada ni se ejecuta una operación por ello. Si no aparece aún, recuperar la conversación desde Conversaciones.
- La conexión de voz y los subtítulos no son prueba de que el cliente escuchó toda la respuesta.
- Si falla el cierre, queda marcado como no confirmado y se permite volver a intentarlo. Si se pierde la respuesta de creación antes de conocer el ID del proveedor, no es posible garantizar el cierre desde ese ID; no se reintenta la creación con la misma clave. Revisar el consumo del proveedor antes de repetir pruebas con fallos de red.
- El cierre por abandono usa una señal del navegador y un plazo de 45 segundos. Hay un límite de cinco minutos y 40 delegaciones por llamada. No se promete un tope exacto de facturación ante fallos del proveedor o del servidor.
- El español usa indicaciones de México (es-MX), coherentes con el escenario MXN: tuteo, ritmo tranquilo y sin voseo ni jerga forzada. Inglés y portugués conservan el idioma elegido; mencionar otra moneda no cambia idioma ni convierte importes. El acento generado debe escucharse en una llamada real; las pruebas del protocolo no acreditan pronunciación.

## Bienvenida breve

Al recibir `session.started`, el servidor envía una sola instrucción de apertura,
con `delegation_id: null`, y registra si el proveedor la acepta. Un acuse confirma
la instrucción, no que el cliente haya escuchado el saludo. No se repite si el
evento de inicio se duplica, ya empezó una conversación o no llega el acuse.

En español: «Hola, soy Nexi, tu agente virtual de Nexqori. Te ayudo a revisar
movimientos, pagos o reclamos. ¿Qué necesitas revisar hoy?». Después escucha y
respeta interrupciones. Hay equivalentes en inglés y portugués. La bienvenida
no usa datos bancarios, no ejecuta el flujo ni cuenta como un mensaje del cliente.

Se mantiene el audio de entrada activo y se manejan el acuse y los errores según
[la secuencia oficial de saludo](https://developers.openai.com/api/docs/guides/live-conversations#greet-before-the-caller-speaks).
Las [indicaciones de idioma y pronunciación](https://developers.openai.com/api/docs/guides/live-prompting)
orientan la voz; hay que validar el acento con el perfil seleccionado.

Fuentes oficiales: [GPT-Live](https://developers.openai.com/api/docs/guides/live), [WebRTC](https://developers.openai.com/api/docs/guides/voice-webrtc), [delegación](https://developers.openai.com/api/docs/guides/live-delegation), [control del servidor](https://developers.openai.com/api/docs/guides/voice-server-controls), [sesiones](https://developers.openai.com/api/docs/guides/live-conversations), [creación](https://developers.openai.com/api/reference/resources/live/methods/create).


## Hallazgos hablados, comparación y expediente (4 de octubre)

Nexi busca movimientos con pistas parciales aunque Jev todavía necesite precisar el tipo de problema. La propuesta no vincula el movimiento hasta que el cliente lo confirma. Las condiciones vigentes del plan permiten calcular la diferencia sin pedir otra vez el precio ya registrado.

La llamada recibe un resumen determinista del servidor: importe, fecha, estado, comparación con la base contractual o promedio y siguiente paso. A petición del usuario, estos datos mínimos se comunican al proveedor de voz para pronunciarlos. No se transmiten nombres de comercios libres, líneas telefónicas, datos de identidad, historial íntegro, documentos, logs ni credenciales. Tampoco se incorporan esos resultados a los modelos de clasificación/extracción. La diferencia acredita un contraste, no fraude ni devolución aprobada; extras o cambios aceptados siguen sujetos a revisión.

El detalle completo y el gráfico se abren únicamente al pulsar **Ver detalle completo**. **Revisar y registrar reclamo** abre el formulario confirmado sin terminar la llamada. Tras guardarlo, se abre **Mis reclamos** con su número de expediente. El servidor detecta el registro y envía una sola notificación hablada, sin confiar en un resultado enviado por el navegador. Los reintentos del registro conservan el mismo caso.

El pago telefónico de prueba sigue pendiente: esta versión propone revisión del supervisor, sin anularlo ni devolver dinero. Para movimientos completados se conserva la solicitud y aprobación administrativa existente. No se han añadido devolución parcial ni cancelación automática.

## Revisión de instrucciones maliciosas con Jev

El usuario autorizó expresamente el envío del texto del mensaje a TypeSafe/Jev para esta revisión. Antes de clasificar o consultar herramientas, se evalúa el texto como dato no confiable. Se ocultan patrones identificables de claves y credenciales; ese filtro no garantiza identificar cualquier secreto pegado por error. No se añaden datos bancarios ni respuestas enriquecidas al payload.

Jev distingue solicitudes habituales (incluidas citas de phishing reportadas) de intentos de alterar instrucciones, impersonar administradores, obtener secretos o saltar confirmaciones. Resultado malicioso: se rechaza ese turno sin modificar la selección ni el checkpoint. Error o confianza menor a 0,7: se pide reformular y no se ejecuta el flujo. El umbral es una decisión inicial de la demo, no una tasa de detección validada. El resultado queda auditado; los mensajes rechazados no entran al historial de los modelos en turnos posteriores.

Esta revisión cubre las delegaciones del chat y de la voz hacia las herramientas del banco. No analiza el audio antes de que GPT-Live lo reciba y no constituye protección absoluta contra prompt injection. El proveedor de voz también recibe reglas para ignorar cambios de autoridad. Titularidad, destinos permitidos, confirmación, idempotencia y aprobación administrativa siguen aplicándose en el servidor aunque un clasificador falle.

Pruebas repetibles: `python -m pytest backend/tests/test_voice_findings.py backend/tests/test_prompt_guard.py -q` y `npm run test:voice:ui`. La primera valida hallazgos, aislamiento, fallos del guard y expediente único. La segunda valida detalle cerrado, gráfico, revisión, navegación y continuidad del micrófono con transporte simulado en ES/EN/PT. Las pruebas de audio reales siguen siendo manuales; un evento enviado al proveedor no acredita que la frase se haya escuchado.
