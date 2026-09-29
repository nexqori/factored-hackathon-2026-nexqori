# Acceso, conversaciones y preferencias

## Identidad y lectura

El login recibe `identifier` (correo o documento) y `password`; `email` sigue siendo un alias de entrada compatible. El correo se normaliza a minúsculas. El documento conserva ceros y letras; normaliza espacios y guiones. El error es genérico y el límite se comparte por cuenta aunque se alternen identificadores. El documento no se devuelve en perfiles ni en el panel admin. Esto no verifica documentos oficiales, buzones ni propiedad de dominios.

Configuración guarda pequeño/mediano/grande en PostgreSQL y cambia la fuente raíz. No hay botón T en el encabezado. El idioma usa un menú con teclado, Escape, cierre exterior, nombres propios y selección visible. ES/EN/PT mantienen igual cobertura.

## Historial independiente

El primer envío crea la conversación y sus dos mensajes en una sola transacción. Nueva limpia la vista sin crear registros vacíos. Conversaciones permite retomar una; la selección permanece al navegar y se limpia al recargar. El texto no enviado se descarta al elegir Nueva u otra conversación.

`POST /api/assistant` acepta `conversationId` opcional y devuelve la conversación y los mensajes guardados junto al comando de navegación. Con ID valida titularidad antes de responder. El listado pagina de 20 en 20; el detalle muestra los últimos 50 mensajes y permite cargar anteriores con `before=<messageId>`. Ese cursor también valida conversación y titular. Una FK compuesta impide asociar mensajes a la conversación de otra persona.

La migración `b721c95d024a` conserva todos los mensajes previos en una conversación por titular, presentada como Conversación anterior. No infiere separaciones históricas inexistentes. Actualiza sólo las direcciones iniciales conocidas, conservando contraseñas, cuentas personalizadas, IDs, contenido y fechas. Para volver al esquema anterior se restaura un respaldo verificado, sin downgrade que descarte conversaciones. Respaldo local de esta intervención: `.local/backups/`, excluido de Git.

## Alcance vigente

La voz queda para otra implementación por decisión de Bryan. Esta base mantiene únicamente el asistente escrito y la operación de consultas y solicitudes bancarias. No contiene captura de audio, motores de voz ni endpoints de transcripción o síntesis.

## Verificación

`npm run test:experience` comprueba documento, teclado, conversaciones separadas, recarga y tamaños de lectura ES/EN/PT. Las pruebas API cubren identificadores, límites compartidos, preferencias, titularidad, paginación y conservación del historial al migrar. `npm run test:ui` recorre el conjunto sobre PostgreSQL en Docker.
