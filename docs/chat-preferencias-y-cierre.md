# Perfil, idioma y cierre documental desde el chat

Actualizado el 4 de octubre de 2026, America/Lima. Extensión del flujo existente, sin reconstruir el maestro.

El chat muestra un formulario con las mismas opciones de Configuración: letra pequeña/mediana/grande, frecuencia bancaria, experiencia digital y acompañamiento. Para nacimiento solicita la fecha, muestra una revisión y exige Confirmar cambio. `/api/profile/field` sólo actualiza el campo confirmado del titular, valida fecha adulta y enumeraciones, exige CSRF y deja auditoría. Estos formularios no pasan por los modelos ni se guardan en localStorage. Los perfiles antiguos sin estos datos completan el formulario existente dentro del chat y revisan todos los valores antes de guardarlos, sin inventar respuestas por defecto.

| Dato | ES | EN | PT |
| --- | --- | --- | --- |
| Letra | Cambia el tamaño de letra | Change my font size | Altere o tamanho da letra |
| Nacimiento | Cambia mi fecha de nacimiento | Change my date of birth | Altere minha data de nascimento |
| Frecuencia | Cambia mi frecuencia bancaria | Change my banking frequency | Altere minha frequência bancária |
| Banca digital | Cambia mi experiencia en banca digital | Change my digital banking experience | Altere minha experiência no banco digital |
| Acompañamiento | Cambia mi preferencia de acompañamiento | Change my support preference | Altere minha preferência de ajuda |

El selector de consulta de tarjeta está dentro del diálogo de contraseña y lista todas las tarjetas disponibles con nombre y terminación. La terminación o un nombre con coincidencia única preseleccionan la tarjeta; también se preselecciona cuando sólo hay una disponible. Una referencia ambigua no elige arbitrariamente. El modelo actual no tiene alias individuales: se muestra Tarjeta Nexqori/Nexqori card/Cartão Nexqori, por lo que dos tarjetas con el mismo nombre exigen elegir la terminación. Cambiar selección descarta la contraseña escrita y cualquier revelación anterior. El bloqueo conserva su diálogo y confirmación existentes.

Mis solicitudes conserva Ver servicios y sus trámites, añade filtro de estado y deja los PDF exclusivamente en Mis documentos. Las traducciones de seguimiento se seleccionan por `kind`, sin modificar estados, auditorías históricas ni operaciones. El formulario documental dice Todas mis solicitudes o Todos mis reclamos según el tipo; cada uno conserva su plantilla y selección propias.

Generar un PDF cierra la conversación de origen. Se informa que hay que iniciar una nueva, se oculta la entrada y ambos endpoints de chat rechazan turnos nuevos con `conversation_closed`. El cierre se deriva del documento persistido, también al recuperar historial; descargarlo y recuperar una respuesta perdida con la misma clave siguen disponibles.

`backend/chat_language.py` comprueba vocabulario del idioma activo antes de comandos e intérprete. Las órdenes conocidas de otro idioma o mezcladas responden pidiendo el idioma de la página, sin avanzar el checkpoint ni llamar a proveedores. Cambiar idioma es la única orden transversal ES/EN/PT. Cifras, referencias y palabras compartidas son neutrales: esta comprobación local no es un detector lingüístico semántico general. Las variantes fuera del vocabulario deben evaluarse antes de ampliar las reglas; no se afirma cobertura de cualquier frase natural imaginable.

Verificación reproducible: `npm run test:chat:profile`, `npm run test:documents:context`, `npm run test:chat:flow` y `backend/tests/test_chat_profile_language.py`. La matriz incluye todos los destinos enumerados, idiomas cruzados, datos confirmados, varias tarjetas, selección por nombre/terminación y cierre de conversación. Los fixtures son aislados; no se modifican perfiles manuales para verificarlos.
