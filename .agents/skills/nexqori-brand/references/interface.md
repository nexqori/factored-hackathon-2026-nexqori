# Criterios de interfaz Nexqori

## Jerarquía
La tarea del cliente domina la pantalla. Una navegación estable permite acceder a inicio, movimientos, productos y solicitudes. El asistente acompaña y propone acciones revisables. Una vista administrativa sólo se añade cuando el encargo la requiere.

Usar Segoe UI/system-ui para controles y lectura; Georgia puede dar calidez a titulares breves. No depender de fuentes externas para funcionar. Cuerpo de 16 px como base, controles de al menos 44 px y títulos con escalado adaptable. No imponer una edad o capacidad a partir del perfil.

## Componentes
- Botón principal: terracota, texto blanco cálido, hover más oscuro, foco claramente visible.
- Botón secundario: superficie clara, texto oscuro y borde perceptible.
- Tarjetas: radios de 16–20 px, bordes suaves y sombras leves sólo si ayudan a separar.
- Dinero: formatear con Intl, código de moneda visible, signo claro; no sumar monedas distintas.
- Solicitudes: referencia estable, motivo, movimiento relacionado, estado y eventos de seguimiento.
- Formularios: etiquetas permanentes; errores en texto junto al campo; no depender de placeholder.
- Diálogos: foco contenido, Escape y cierre sin ejecutar. Confirmar antes de cambiar estado.
- Tablas/listas: simplificar en móvil manteniendo importe, estado y acción accesibles.
- Sin datos o sin resultados: explicar el estado y ofrecer limpiar filtros o volver.

## Semántica
Éxito verde apagado y advertencia ocre son auxiliares, no nuevos colores de marca. Acompañar siempre con texto/icono. Evitar gradientes saturados, brillo, decoración que compita con importes y avisos, y promesas de seguridad absoluta.

## Contenido de producto
Fixtures diseñados para la demo, separados del dataset del hackathon. El EDA mostró incoherencias caso–producto y textos repetitivos; no convertir esas fuentes en hechos individuales fiables. La cuenta y los movimientos de la demo deben enlazar por IDs coherentes. La base tiene autenticación y permisos de servidor; su auditoría local no es inmutable ni una certificación bancaria.

La interfaz no debe mostrar etiquetas de demo, simulación o datos ficticios. Usar un tono natural; distinguir una solicitud registrada de una operación completada. Los límites del entorno se documentan técnicamente.

El asistente base puede resolver consultas por reglas, pedir precisión o preparar una derivación. No diagnosticar fraude a partir de una palabra. Registrar un reclamo no significa resolver la disputa ni devolver dinero.

## Tres idiomas
Traducir desde el inicio ES/EN/PT con igual cobertura. Conservar la preferencia al recargar e iniciar sesión; una elección explícita en login puede reemplazar la preferencia guardada. No traducir IDs, referencias, nombres propios ni códigos de moneda. Adaptar textos, fechas, separadores y etiquetas accesibles; comprobar desbordamientos con las tres longitudes. El historial conserva el idioma original por mensaje.
