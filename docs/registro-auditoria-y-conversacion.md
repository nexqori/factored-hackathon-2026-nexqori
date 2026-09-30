# Registro, auditoría y conversación

Implementación en `bryan`, 30 de septiembre de 2026. Banco: http://localhost:5180. LAB: http://localhost:5190.

## Registro y experiencia

El acceso ofrece Correo ✉️ y Documento 🪪, más Crear mi perfil. El registro solicita nombre, correo, documento, fecha de nacimiento, contraseña de 12–128 caracteres y confirmación; después recoge experiencia bancaria/digital, preferencia de acompañamiento, idioma y tamaño de letra. El servidor fija el rol cliente, normaliza correo/documento, evita duplicados, valida 18–120 años y crea una sesión con cookie HttpOnly y CSRF. Contraseñas con Argon2. No abre cuentas ni asigna dinero o tarjetas.

`customer_profiles` conserva la fecha y las preferencias declaradas. Los grupos 18–49, 50–59 y 60+ se calculan al consultar. La edad no cambia permisos ni activa ayuda por sí sola. En modo automático, poca experiencia bancaria o digital propone orientación; el cliente puede elegir orientación o acceso directo en Configuración. Usuarios anteriores no reciben una fecha de nacimiento inventada. No se verifica identidad oficial, correo ni elegibilidad de productos; MFA, recuperación y verificación de identidad siguen fuera de esta base.

## Auditoría del banco

Administración incluye una tabla paginada de 50 eventos, filtro por usuario/actor y actividad, fecha/hora, persona que realizó la acción, cliente, folio y enlace a la conversación. Registra login exitoso, logout, registro, preferencias de experiencia, consulta protegida de tarjeta, solicitud, revisión, derivación, navegación del asistente, inicio de conversación, mensaje del cliente y respuesta. La respuesta del asistente se vincula al cliente que inició el turno; el tipo de evento identifica que la produjo el sistema.

Los administradores pueden consultar mensajes paginados. Cada consulta agrega `conversation_viewed`, con administrador como actor y cliente como titular. Clientes y anónimos no pueden usar estas rutas. Los registros históricos sin vínculo de conversación siguen conservados, sin inventar asociaciones.

- `GET /api/admin/audit?userId=…&action=…&offset=…`
- `GET /api/admin/conversations/{id}?before=…`

`audit_events` guarda referencias, no duplicados de conversaciones ni secretos de autenticación/tarjetas. Los mensajes viven en `messages`. No hay eliminación desde la interfaz. Esta auditoría local no es un registro inmutable, SIEM, control de retención ni cobertura de todos los intentos fallidos; esos controles requieren una implementación posterior. No se exportan conversaciones del banco a Jev/OpenAI.

## Texto pegado y llamada

Al pegar texto de al menos 200 caracteres o cuatro líneas, el compositor muestra una tarjeta expandible y permite quitarla. El envío conserva el texto completo y la instrucción; no lo ejecuta como código, no renderiza HTML y no lo manda hasta pulsar Enviar. Si supera el límite, informa el error sin truncarlo: 8.000 caracteres combinados en banco; 1.900 en el compositor del LAB, dejando espacio para el delimitador dentro de su contrato de 2.000 por mensaje. Al fallar el envío se conserva el borrador. Texto y adjunto se limpian al cambiar de conversación o al enviar correctamente.

Iniciar llamada abre únicamente la presentación de la función en preparación, con mini bot y regreso al chat. No solicita micrófono, no captura audio, no simula conexión y no instala Whisper ni otros motores.

## Jev → contrato → Luna en el LAB

Hay dos acciones distintas:

1. **Ejecutar caso**: Jev y Luna clasifican la misma conversación. Luna no recibe la predicción de Jev. Se muestran errores, modelo, latencia y consumo; no se presenta probabilidad inventada para Luna.
2. **Probar respuesta de este caso**: Jev selecciona la categoría y el servidor carga su contrato. Luna recibe conversación, contrato, contexto declarado e instrucciones personalizadas para redactar el siguiente paso. No recibe herramientas ni acceso al banco. Cada nuevo mensaje vuelve a clasificarse con el contexto anterior; máximo diez mensajes, sin recorte silencioso.

`backend/workflow_catalog.json` define seis procedimientos versionados: cargo no reconocido, importe incorrecto, estado del pago, problemas de app, sucursal y calidad de servicio. Las otras categorías tienen orientación de catálogo, identificada como `guidance`, no un procedimiento bancario completo. Las instrucciones adicionales se guardan por categoría e idioma en `.local/intent-lab/workflow-instructions.json`. Seleccionar una categoría en el editor no fuerza la decisión de Jev. El enlace opcional al banco sólo abre una ruta permitida; no copia conversación ni registra una operación.

Los registros privados `.local/intent-lab/runs/{uuid}.json` permiten revisar entrada, clasificación, contrato/versiones, hash de instrucciones, respuesta, tokens, latencia y errores. Las conversaciones encadenadas comparten `thread_id`. El actor se denomina operador local: el LAB no tiene autenticación de usuarios y debe seguir enlazado sólo a loopback. No publicar estos archivos ni usar datos sensibles en los casos.

OpenAI usa Responses API, `gpt-6-luna`, razonamiento `high`, `store:false`, salida JSON estricta, timeout y endpoint oficial fijo. Claves sólo en `providers.env` privado; no hay sustitución de modelo ni reintentos automáticos. `store:false` no sustituye las políticas de tratamiento de datos del proveedor. Acuerdo entre modelos sigue requiriendo revisión: no hay umbrales calibrados ni autorización automática.

Prueba real del 30/09: los cinco diálogos diseñados acertaron su etiqueta con ambos modelos (5/5 cada uno); una respuesta para cargo no reconocido utilizó su contrato sin afirmar una operación ejecutada. Es una comprobación funcional pequeña, no benchmark representativo. Los textos originales del dataset siguen separados y no se enviaron en estas pruebas.

## Actualizar y verificar

Respaldar PostgreSQL y ejecutar `docker compose up --build -d`, sin borrar volúmenes. `e104b56a902c` añade perfiles y actualiza exclusivamente la terminación de la tarjeta fixture; `f217a8e309bc` enlaza auditoría/conversación. Los hashes previos/posteriores de usuarios, movimientos, solicitudes y mensajes coincidieron al aplicar la migración de registro, antes de las pruebas UI.

Ejecutar las comprobaciones de AGENTS.md y `node scripts/nexqori-registration-audit.mjs`. Los recorridos del banco deben correr en serie; crean actividad ficticia marcada Verificación. Los tests unitarios del LAB usan transportes HTTP controlados y no necesitan claves. Las pruebas reales de proveedores son separadas y sus salidas permanecen locales.
