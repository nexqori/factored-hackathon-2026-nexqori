# Agente de navegación

La base ya interpreta pedidos de navegación en español, inglés y portugués. Usa reglas locales deterministas: **no hay un LLM conectado**. Los mensajes y el idioma se guardan por usuario. El frontend envía sólo el identificador permitido de la pantalla actual como contexto; el historial se muestra, pero todavía no se usa para razonamiento conversacional libre.

Ejemplos: “Llévame a transferencias”, “Show my cards”, “Abrir empréstimos”, “¿Cuál es mi saldo?”. Un pedido de revisión abre el formulario de solicitud. Una petición desconocida pide precisión; la navegación no crea solicitudes ni mueve dinero.

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

## Incorporar un modelo después

Añadir un adaptador en servidor que reciba mensaje, locale y contexto autorizado, y devuelva texto o una propuesta de herramienta. Registrar el esquema de `NAVIGATION_TOOL`, validar su salida con `NavigateInput` y resolver permisos desde la sesión. Mantener timeouts, error localizable y fallback guiado. Las claves del proveedor permanecen fuera de React y Git.

El contexto del modelo sólo debe incluir datos autorizados del usuario. Un documento o mensaje puede aportar información, pero no cambiar permisos, identidad o instrucciones de aplicación. El modelo no confirma acciones por el cliente: pagos, bloqueos o contrataciones requerirían servicios propios, política explícita, confirmación fuera del chat, idempotencia y comprobación posterior. No están implementados en esta base.

La reproducción de respuestas usa `speechSynthesis` del navegador, sujeta a las voces instaladas. No hay captura de micrófono, transcripción ni servicio de voz conectado.

## Tono de la interfaz

Por indicación de Bryan, las pantallas y respuestas utilizan lenguaje natural de producto, sin etiquetas de demo o simulación. Un caso registrado se describe como solicitud enviada a atención; no se afirma que una persona haya respondido ni que una operación monetaria se ejecutó. Las respuestas históricas generadas con las plantillas anteriores se presentan con el tono actual mediante una correspondencia exacta; su contenido original permanece en PostgreSQL y los mensajes escritos por usuarios no se modifican.
