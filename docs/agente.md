# Agente de navegación

Actualización del 2 de octubre: [chat conectado al banco, pago de teléfono con comprobante y sección Mis reclamos](chat-bancario-y-pagos.md). Esta ampliación sustituye las limitaciones anteriores que indicaban que el chat sólo navegaba y que teléfono sólo registraba solicitudes. Los demás servicios conservan su alcance.

La base ya interpreta pedidos de navegación en español, inglés y portugués. Usa reglas locales deterministas: **no hay un LLM conectado al chat bancario**. Los mensajes y el idioma se guardan por conversación y titular. El frontend envía la pantalla permitida y, al elegir Preguntar por este movimiento, su ID; el servidor valida titularidad y conserva el movimiento en esa conversación. El historial se muestra, pero todavía no se usa para razonamiento conversacional libre.

Este límite corresponde al chat del banco. El LAB separado implementa Jev → contrato → Luna y comparación independiente; mantiene sus conversaciones separadas. El editor de flujos puede usar la sesión bancaria del mismo navegador para lecturas del titular mediante un adaptador limitado; los tokens y respuestas bancarias no se envían a modelos. El chat bancario admite texto pegado como tarjeta previa al envío y una presentación de llamada sin captura de audio. La consulta de conversaciones por administración deja un evento de auditoría. Véase [guía de registro y conversación](registro-auditoria-y-conversacion.md).

El [enrutador compartido de consultas/problemas](enrutamiento-jev-herramientas.md) convierte la intención de Jev en un plan de herramientas. El editor puede ejecutar lecturas en Contexto y conserva las operaciones como propuestas; el banco dispone de un gateway de siete lecturas propias con sesión, CSRF y auditoría. Las herramientas de preparación no son comandos financieros y el gateway las rechaza. Todavía no hay adaptador Jev en el chat autenticado.

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

Destinos: home, products, movements, requests, services, help, accounts, cards, transfers, payments, loans, investments, insurance, cash, settings. Cuentas y tarjetas filtran productos; las categorías abren un catálogo buscable. Un servicio específico usa `destination=services`, `serviceId` registrado y una ruta derivada `/services/catalog/{id}`; ambos extremos rechazan IDs o rutas ajenos al catálogo. No hay destino admin ni URL externa. La auditoría registra que se emitió el comando; el navegador puede fallar después y ese registro no acredita apertura exitosa.

## Incorporar un modelo después

Añadir un adaptador en servidor que reciba mensaje, locale y contexto autorizado, y devuelva texto o una propuesta de herramienta. Registrar el esquema de `NAVIGATION_TOOL`, validar su salida con `NavigateInput` y resolver permisos desde la sesión. Mantener timeouts, error localizable y fallback guiado. Las claves del proveedor permanecen fuera de React y Git.

El contexto del modelo sólo debe incluir datos autorizados del usuario. Un documento o mensaje puede aportar información, pero no cambiar permisos, identidad o instrucciones de aplicación. El modelo no confirma acciones por el cliente. Bloqueo y devolución tienen [servicios propios](acciones-problemas.md), confirmación fuera del chat, titularidad, idempotencia y auditoría; la devolución requiere decisión administrativa. Sus efectos son locales. Pagos externos y contrataciones no están implementados.


## Tono de la interfaz

Por indicación de Bryan, las pantallas y respuestas utilizan lenguaje natural de producto, sin etiquetas de demo o simulación. Un caso registrado se describe como solicitud enviada a atención; no se afirma que una persona haya respondido ni que una operación monetaria se ejecutó. Las respuestas históricas generadas con las plantillas anteriores se presentan con el tono actual mediante una correspondencia exacta; su contenido original permanece en PostgreSQL y los mensajes escritos por usuarios no se modifican.

## Descubrir un servicio

“Quiero pagar celular”, “Pay my phone bill” y “Pagar celular” abren Empresa Telefónica. La búsqueda usa el mismo catálogo que la pantalla Servicios; el proveedor nunca sale del texto libre del chat. El comando sólo abre el formulario: datos, revisión y confirmación permanecen en la interfaz. Una consulta genérica como “Servicios” mantiene el catálogo completo.

Las conversaciones se abren por elección del usuario; véase [acceso y conversaciones](acceso-y-conversaciones.md). La voz se implementará en otro flujo, sin motores ni endpoints activos en esta base.
