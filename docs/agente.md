# Agente de navegación

La base ya interpreta pedidos de navegación en español, inglés y portugués. Usa reglas locales deterministas: **no hay un LLM conectado**. Los mensajes y el idioma se guardan por usuario. El frontend envía sólo el identificador permitido de la pantalla actual como contexto; el historial se muestra, pero todavía no se usa para razonamiento conversacional libre.

Ejemplos: “Llévame a transferencias”, “Show my cards”, “Abrir empréstimos”, “¿Cuál es mi saldo?”. Un pedido de revisión abre el formulario de solicitud. Una petición desconocida pide precisión; la navegación no crea solicitudes ni mueve dinero.

## Seguimiento por inactividad

Tras cinco minutos sin interacción en una conversación iniciada, la interfaz selecciona al azar una pregunta NPS, CSAT o CES. NPS acepta 0–10, CSAT 1–5 con emojis y CES 1–7. Enviar guarda la respuesta; después se reinicia la conversación visible y reaparecen el saludo y las cuatro intenciones iniciales. La opción para continuar conserva el historial visible y reinicia el contador. La sesión autenticada permanece abierta y los mensajes ya guardados en el servidor no se eliminan.

Cada envío registra el idioma, la métrica, la puntuación, el tiempo desde que apareció la pregunta hasta el envío y el tiempo desde el primer mensaje de la conversación hasta la respuesta. La clave de envío hace idempotentes los reintentos. El panel de administración sólo muestra resultados agregados: NPS (promotores 9–10 menos detractores 0–6), CSAT (porcentaje de respuestas 4–5), promedio CES, volumen de respuestas y tiempos medios. No se muestran respuestas individuales.

## Herramienta

`backend/navigation.py` expone `NAVIGATION_TOOL`, `NavigateInput` y `navigate_in_app`. La autorización parte de la sesión en `/api/assistant`, reservada al cliente. `src/navigation.ts` valida nuevamente herramienta, destino y ruta; no ejecuta una URL procedente del chat.

```json
{
  "tool": "navigate_in_app",
  "destination": "transfers",
  "route": "/services/transfers"
}
```

Destinos: home, products, movements, requests, services, help, accounts, cards, transfers, payments, loans, investments, insurance, cash. Cuentas y tarjetas filtran productos; seis servicios tienen pantallas propias y solicitudes con servicio seleccionado. No hay destino admin ni URL externa. La auditoría registra que se emitió el comando; el navegador puede fallar después y ese registro no acredita apertura exitosa.

### Mapeo provisional de intenciones

Mientras no se conecte el LLM, `src/intent-router.ts` traduce las intenciones actuales del agente a destinos de la lista permitida: `movements` → `movements` (`/movements`), `requests` → `requests` (`/requests`), `report` → `requests` (`/requests`) y `cards` → `cards` (`/products?kind=cards`). Por ello, iniciar una solicitud o presentar un reclamo dirige a “Mis solicitudes”; esa pantalla permite comenzar el formulario. No hay una pantalla ni un destino independiente para reclamos. El helper usa React Router y contiene errores notificándolos a la interfaz. El mapeo puede reemplazarse cuando se conecte el modelo, manteniendo destinos permitidos.

## Incorporar un modelo después

Añadir un adaptador en servidor que reciba mensaje, locale y contexto autorizado, y devuelva texto o una propuesta de herramienta. Registrar el esquema de `NAVIGATION_TOOL`, validar su salida con `NavigateInput` y resolver permisos desde la sesión. Mantener timeouts, error localizable y fallback guiado. Las claves del proveedor permanecen fuera de React y Git.

El contexto del modelo sólo debe incluir datos autorizados del usuario. Un documento o mensaje puede aportar información, pero no cambiar permisos, identidad o instrucciones de aplicación. El modelo no confirma acciones por el cliente: pagos, bloqueos o contrataciones requerirían servicios propios, política explícita, confirmación fuera del chat, idempotencia y comprobación posterior. No están implementados en esta base.

La reproducción de respuestas usa `speechSynthesis` del navegador, sujeta a las voces instaladas. No hay captura de micrófono, transcripción ni servicio de voz conectado.

## Tono de la interfaz

Por indicación de Bryan, las pantallas y respuestas utilizan lenguaje natural de producto, sin etiquetas de demo o simulación. Un caso registrado se describe como solicitud enviada a atención; no se afirma que una persona haya respondido ni que una operación monetaria se ejecutó. Las respuestas históricas generadas con las plantillas anteriores se presentan con el tono actual mediante una correspondencia exacta; su contenido original permanece en PostgreSQL y los mensajes escritos por usuarios no se modifican.
