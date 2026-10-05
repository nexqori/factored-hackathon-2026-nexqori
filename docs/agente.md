# Agente de navegación

El chat y el editor usan [LangGraph para planificar el flujo](langgraph-atencion.md). Cada bloque es un nodo; preguntas, continuidad y herramientas conservan los contratos y checkpoints existentes. El framework no autoriza operaciones financieras.

Integración del 2 de octubre: [pagos y transferencias](pagos-y-transferencias.md), [consultas y PDF](consultas-y-documentos.md) y [continuidad de conversación](contexto-conversacion.md). Pagos y transferencias se guardan en Movimientos; documentos pedidos y trámites, en Mis solicitudes; problemas, en Mis reclamos.

El chat interpreta consultas, problemas y servicios en español, inglés y portugués. Usa Jev y Luna con configuración privada del servidor, además del recorrido guiado disponible sin proveedores. Los mensajes y el idioma se guardan por conversación y titular. El frontend envía la pantalla permitida y, al elegir Preguntar por este movimiento, su ID; el servidor valida titularidad y conserva el movimiento en esa conversación. El historial seguro conserva el tema y las aclaraciones. Las respuestas visibles con saldos o transacciones no se copian al contexto del modelo.

El LAB comparte el motor Jev → contrato → Luna y mantiene sus conversaciones de evaluación separadas. El editor de flujos puede usar la sesión bancaria del mismo navegador para lecturas del titular mediante un adaptador limitado; los tokens y respuestas bancarias no se envían a modelos. El chat bancario admite texto pegado como tarjeta previa al envío y una presentación de llamada sin captura de audio. La consulta de conversaciones por administración deja un evento de auditoría. Véase [guía de registro y conversación](registro-auditoria-y-conversacion.md).

El [enrutador compartido de consultas/problemas](enrutamiento-jev-herramientas.md) convierte la intención de Jev en un plan de herramientas. El editor puede ejecutar lecturas en Contexto y conserva las operaciones como propuestas; el banco dispone de un gateway de siete lecturas propias con sesión, CSRF y auditoría. Las herramientas de preparación no son comandos financieros y el gateway las rechaza. El chat autenticado usa el mismo flujo maestro con checkpoints persistidos por conversación.

Ejemplos: “Llévame a transferencias”, “Show my cards”, “Abrir empréstimos”, “¿Cuál es mi saldo?”. Un pedido de revisión abre el formulario de solicitud. Una petición desconocida pide precisión; la navegación no crea solicitudes ni mueve dinero.

## Resolución y evaluación de la atención

La contribución de Araceli se integra en el chat y expediente actuales. Una resolución confirmada y sin gestiones pendientes programa el cierre de atención para dentro de 15 minutos. El servidor conserva el plazo, revisa cambios y procesa respuestas parciales o ausentes sin inventar puntuaciones. No se cierra por inactividad ni se borra u oculta el chat. Los reclamos requieren confirmación administrativa; las consultas terminadas pueden ser confirmadas por el titular. El cierre de atención no ejecuta ni modifica operaciones financieras.

El formulario vinculado al titular y caso o conversación contiene NPS 0–10, satisfacción CSAT 1–5, esfuerzo CES 1–7 opcional y comentario opcional. Permite guardar una respuesta parcial y terminarla después del cierre. Los envíos completos alimentan los agregados de Araceli sin duplicarse; los campos ausentes no son cero. Administración puede revisar respuestas individuales dentro del expediente autorizado. Los tiempos de formularios nuevos quedan sin medición; no se mezclan como ceros en las medias históricas. Véase [formularios y cierre](formularios-y-cierre.md).

## Herramienta

`backend/navigation.py` expone `NAVIGATION_TOOL`, `NavigateInput` y `navigate_in_app`. La autorización parte de la sesión en `/api/assistant`, reservada al cliente. `src/navigation.ts` valida nuevamente herramienta, destino y ruta; no ejecuta una URL procedente del chat.

```json
{
  "tool": "navigate_in_app",
  "destination": "transfers",
  "route": "/services/transfers"
}
```

Destinos: home, products, movements, requests, services, help, accounts, cards, transfers, payments, loans, investments, insurance, cash, settings. Cuentas filtra productos; tarjetas abre `/cards` y activa su entrada del menú. Las categorías abren un catálogo buscable. Un servicio específico usa `destination=services`, `serviceId` registrado y una ruta derivada `/services/catalog/{id}`; ambos extremos rechazan IDs o rutas ajenos al catálogo. No hay destino admin ni URL externa. La auditoría registra que se emitió el comando; el navegador puede fallar después y ese registro no acredita apertura exitosa.

## Órdenes explícitas de aplicación

`backend/chat_commands.py` añade reglas ES/EN/PT antes de avanzar el intérprete, sin reconstruir el maestro. Distingue abrir Mis solicitudes de abrir Mis reclamos y reconoce tarjetas, Inicio y Centro de ayuda. Los comandos guardan mensajes, auditoría y respuesta idempotente en el chat conectado, preservando íntegro el checkpoint, contrato, referencias y pregunta pendiente. No consumen proveedores ni se incorporan al historial del modelo. Una respuesta posterior al caso continúa desde el punto guardado.

Cambiar a Español, English o Português devuelve un comando limitado que la interfaz aplica con `PATCH /api/profile/locale`; cerrar sesión utiliza `POST /api/auth/logout`, con sus permisos, CSRF y auditoría existentes. El reconocimiento requiere una orden completa del texto escrito por el cliente; no acepta texto pegado, negaciones, instrucciones citadas ni salidas del modelo como autorización. No ejecuta operaciones bancarias. Las variantes fuera de estas reglas conservan el intérprete existente; no es una clasificación semántica ilimitada.

Validación: `backend/tests/test_chat_commands.py` comprueba variantes, aislamiento, reintentos y continuidad. `npm run test:chat:flow` añade navegación y menú activo durante una pregunta pendiente, cambios de idioma persistidos tras recarga y cierre de sesión real en los tres idiomas.

## Proveedores y contexto

El adaptador del servidor recibe mensaje, locale e historia segura. La salida del proveedor nunca define permisos ni SQL. Las rutas se validan con `NavigateInput`; se conservan timeouts, errores localizables y recorrido guiado. Las claves del proveedor permanecen fuera de React y Git.

El contexto del modelo conserva el relato del usuario, el tema de la consulta y la pregunta pendiente; excluye registros bancarios agregados por la aplicación. Véase [control de contexto](contexto-conversacion.md). Un documento o mensaje puede aportar información, pero no cambiar permisos, identidad o instrucciones de aplicación. El modelo no confirma acciones por el cliente. Bloqueo y devolución tienen [servicios propios](acciones-problemas.md), confirmación fuera del chat, titularidad, idempotencia y auditoría; la devolución requiere decisión administrativa. Sus efectos son locales. Pagos externos y contrataciones no están implementados.


## Tono de la interfaz

Por indicación de Bryan, las pantallas y respuestas utilizan lenguaje natural de producto, sin etiquetas de demo o simulación. Un caso registrado se describe como solicitud enviada a atención; no se afirma que una persona haya respondido ni que una operación monetaria se ejecutó sin comprobante del servidor. Las respuestas históricas generadas con las plantillas anteriores se presentan con el tono actual mediante una correspondencia exacta; su contenido original permanece en PostgreSQL y los mensajes escritos por usuarios no se modifican.

## Descubrir un servicio

“Quiero pagar celular”, “Pay my phone bill” y “Pagar celular” abren Empresa Telefónica. La búsqueda usa el mismo catálogo que la pantalla Servicios; el proveedor nunca sale del texto libre del chat. El comando sólo abre el formulario: datos, revisión y confirmación permanecen en la interfaz. Una consulta genérica como “Servicios” mantiene el catálogo completo.

Las conversaciones se abren por elección del usuario; véase [acceso y conversaciones](acceso-y-conversaciones.md). La llamada opcional usa el mismo intérprete y conserva el caso; se habilita mediante `compose.voice.yaml`. Véase [voz y límites](voz-gpt-live.md).

Perfil, selector de tarjetas, idioma activo y cierre tras PDF: [guía y pruebas](chat-preferencias-y-cierre.md).
