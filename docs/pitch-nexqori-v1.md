# Nexqori · primer guion de pitch

Versión de trabajo · 3 de octubre de 2026. Alternativa inicial para ensayar; no es una presentación final ni una promesa de resultados comerciales.

## Idea central

**Tu banco ya tiene parte de la respuesta. Nexqori la reúne contigo y te ayuda a dar el siguiente paso.**

Una persona ve un cobro extraño. No sabe si pagó de más, si el pago falló o si necesita proteger su tarjeta. Hoy puede terminar repitiendo su historia. Nexqori conserva la conversación, consulta sus propios registros y prepara una acción que la persona puede revisar y confirmar.

## Tres problemas para mostrar, en este orden

La prioridad es narrativa y capacidad de demostración, no un ranking estadístico de los tres motivos más frecuentes. Las personas son fixtures del proyecto inspirados en familias del EDA, no clientes extraídos del dataset.

| Caso y usuario | Primera frase | Qué mostrar en pantalla | Valor para el cliente y el banco |
|---|---|---|---|
| **1. Cobro excesivo · Diego** | «Me cobraron 459 pesos de Internet Plus y esperaba pagar 299. ¿Por qué pagué más?» | Identificación del movimiento, importe esperado, diferencia de MXN 160, antecedentes comparables si existen, resumen confirmado y caso en Mis reclamos. | El cliente entiende qué se encontró y atención recibe un expediente con contexto. |
| **2. Cargo no reconocido · Camila** | «No reconozco este cobro de 185 pesos. Tengo mi tarjeta conmigo.» | Confirmar el cargo correcto, registrar el reclamo y mostrar su identificador. Como acción separada y explícita, abrir Tarjetas y confirmar el bloqueo con contraseña. | El cliente puede proteger su tarjeta y conservar el seguimiento del cargo. |
| **3. Pago descontado y pendiente · Valeria** | «Pagué 299 pesos de teléfono. Se descontó, pero sigue pendiente. ¿Tengo que pagar otra vez?» | Movimiento pendiente y comprobante, explicación del estado, revisión registrada y seguimiento. Comprobar que no aparece un segundo débito. | Reduce la incertidumbre y evita una repetición innecesaria del pago. |

En el primer caso, no mostrar un promedio de 299 si la cuenta no tiene esos antecedentes. El grupo compartido no garantiza tres pagos comparables; la app debe indicar historial insuficiente. Camila tiene además un caso local adicional de 459/299 preparado anteriormente: no confundirlo con su cargo de 185 ni afirmar que ese registro adicional existe en todas las instalaciones.

## Ensayo de los casos

1. Abrir los accesos locales de `.local/ux-users/equipo-ux/INICIAR.private.md`. Las credenciales no forman parte de las diapositivas ni del repositorio.
2. Entrar con el usuario correspondiente y abrir Nueva conversación. Usar el movimiento principal indicado en su guía privada. Confirmar que coincide en comercio, importe y referencia.
3. En cobro excesivo, aclarar «No cambié de plan ni contraté un servicio adicional» sólo como parte del escenario ficticio. Revisar que el resumen conserve la diferencia y la aclaración.
4. Revisar el resumen y confirmar el reclamo. Mostrar el caso en Mis reclamos y su estado real. El alta de un reclamo no equivale a resolverlo ni devolver dinero.
5. Si se muestra devolución, solicitarla y cambiar a administrador para revisar/aprobar. Mostrar el identificador de operación y el abono al mismo titular. No atribuir esa aprobación al bot.
6. Para el cargo desconocido, bloquear únicamente la tarjeta ficticia elegida y sólo al final del ensayo: el bloqueo es persistente. No dar por hecho que el chat la bloqueó.
7. Para el pago pendiente, mostrar que el débito permanece único y el caso queda registrado. Este entorno no liquida pagos con una telefónica externa ni resuelve el pendiente al esperar.

Repetir sobre el mismo movimiento puede recuperar o vincular el caso ya existente. Para una grabación limpia, preparar otro grupo con `node scripts/prepare-ux-users.mjs --confirm-local --pack=pitch-ensayo-01`; repetir ese comando conserva el grupo, no lo reinicia. No borrar la actividad de los usuarios manuales.

## Alternativa breve: documento descargable

**Sofía:** «Quiero los movimientos del mes pasado y un estado de cuenta en PDF».

Mostrar el periodo conservado, los filtros en Movimientos, la revisión de parámetros y la descarga desde Mis documentos. Es una buena alternativa de 20–30 segundos para enseñar una consulta completada sin abrir un reclamo. El archivo es informativo, no una constancia certificada.

## Video: primera alternativa de 3 minutos

La imagen compartida por el equipo organizador recomienda 90 % producto/creatividad y 10 % técnica. Los tres minutos siguientes son una propuesta de edición, no un límite oficial confirmado.

| Tiempo propuesto | Historia y plano |
|---|---|
| 0:00–0:20 | Notificación de cobro y reacción del cliente: «Esperaba 299. Me cobraron 459. ¿Qué hago ahora?». Presentar el problema antes de la tecnología. |
| 0:20–0:35 | Aparece Nexqori: una conversación que conserva lo que ya explicaste. Marca, interfaz y promesa concreta. |
| 0:35–1:25 | Caso principal de cobro excesivo: movimiento → hallazgos → confirmación → caso visible. Cortes breves; destacar la diferencia y el siguiente paso. |
| 1:25–2:05 | Montaje de cargo desconocido y pago pendiente: proteger tarjeta con confirmación y revisar un pago sin repetir el débito. |
| 2:05–2:30 | Continuidad: el cliente vuelve al mismo caso y atención encuentra el contexto. Mostrar trazabilidad, no una consola técnica. |
| 2:30–2:48 | Una lámina sencilla: conversación → clasificación → registros propios → acción confirmada → seguimiento. |
| 2:48–3:00 | Cierre: «Nexqori. Entiende lo que pasó. Decide el siguiente paso.» |

Usar planos de producto, acercamientos a hallazgos y transiciones entre estados. Una grabación de pantalla puede servir de material, pero el montaje debe contar una historia. Identificar animaciones conceptuales para que no parezcan funciones ejecutadas.

## Diapositivas: alternativa inicial de 8 láminas

La guía compartida propone 60 % producto/creatividad y 40 % técnica; distribuir el tiempo y el contenido con esa intención.

1. **El problema:** incertidumbre ante un cobro y repetición del relato.
2. **La oportunidad observada:** cifras agregadas del EDA con denominador y límites.
3. **El producto:** una conversación, registros propios y un siguiente paso revisable.
4. **El caso principal:** cobro de 459 frente a 299 esperados; hallazgos y seguimiento.
5. **Dos momentos de valor:** protección de tarjeta y pago pendiente sin segundo débito.
6. **Cómo funciona:** Jev clasifica, LangGraph conserva el flujo, los contratos definen evidencia y permisos; LLM ayuda con contexto y preguntas.
7. **Confianza y evaluación:** aislamiento por titular, confirmación, idempotencia y auditoría. Pruebas de software no equivalen a precisión del modelo ni a ahorro comercial demostrado.
8. **Siguiente validación:** usuarios, resolución por caso, tiempo hasta el siguiente paso, derivaciones útiles y satisfacción; pedir un piloto acotado, sin inventar métricas de retorno.

## Evidencia que puede citarse

- El EDA registra **12.297 reclamos por cargo no reconocido** y **12.194 por cobro indebido**. Las categorías conocidas tienen volúmenes cercanos; no decir que uno domina el dataset.
- Queja + Técnico reúnen **96.940 de 160.266 contactos no resueltos (60,49 %)**. Es una oportunidad observada, no el porcentaje que Nexqori ya resuelve.
- Phone representa **583.250 de 686.296 contactos (84,99 %)**. Justifica explorar continuidad de voz; no demuestra que GPT-Live sea superior ni disponible en nuestra cuenta.

Fuentes del repositorio: [análisis de servicios](servicios-basados-en-datos.md), [reclamos](../notebooks/servicios_nexqori/complaint_needs.csv), [contactos](../notebooks/servicios_nexqori/contact_needs.csv), [canales](../notebooks/servicios_nexqori/contact_channels.csv), [usuarios para pruebas](usuarios-prueba-ux.md) y [comparación histórica](comparacion-historica-pagos.md).

## Voz y límites de la entrega

La voz reutiliza el flujo del chat. La integración está construida; la prueba de acceso del 3 de octubre encontró clave válida pero `gpt-live-1` no disponible (404 y sin modelos de voz en el catálogo accesible). La llamada real queda bloqueada por ese acceso y no se debe presentar como validada. El pitch puede usar texto hasta habilitar y probar la cuenta. Ver [guía de voz](voz-gpt-live.md).

La banca es un libro local de pruebas. No hay recaudador externo, operador humano conectado automáticamente ni devoluciones automáticas. El valor que sí se puede demostrar es contexto, evidencia consultada, decisiones revisables y trazabilidad.

## Siguiente ampliación acordada: comportamiento de gastos

Pendiente de construir y validar. Ampliará la comparación puntual de un cobro a un perfil de gastos de cada uno de los cinco usuarios.

Flujo propuesto: **historial del titular → comprobación de datos suficientes → gastos habituales → evaluación del nuevo cargo → advertencia → política de protección → reconocimiento del cliente o reclamo**.

- Revisar primero la cantidad, fechas, monedas, comercios y estados disponibles. Cinco personas no garantizan historial suficiente para entrenar o evaluar ML.
- Comparar importe, frecuencia y comercio dentro del historial propio. Mostrar el periodo y los pagos usados en la comparación.
- Separar un importe mayor, un comercio nuevo y varios cargos en poco tiempo. Una señal no confirma por sí sola un error ni fraude.
- Comparar una base de reglas estadísticas explicables con un detector ML si el volumen y la calidad permiten una evaluación útil.
- Preparar casos normales y fuera de tendencia con resultado esperado para los cinco perfiles. Si se amplían los fixtures, identificarlos como datos construidos para evaluación; no presentarlos como transacciones reales del dataset.
- Medir alertas correctas, falsas alertas, casos sin datos suficientes y tiempo de respuesta. El detector entrega señales; las reglas del servidor deciden la protección. El modelo de lenguaje no concede permisos ni ordena operaciones financieras.

### Advertencia y bloqueo preventivo solicitados

También pendiente de construir. La advertencia aparecerá en la app con el movimiento, motivo y comparación. Un criterio de riesgo definido y probado podrá activar un bloqueo temporal de la tarjeta correspondiente hasta que el titular revise el gasto. Un aumento de importe aislado no acredita fraude; los criterios deben evaluarse con casos normales y falsos positivos antes de activarlos.

- **Lo reconozco:** reautenticar al titular, registrar la decisión y levantar únicamente el bloqueo preventivo vinculado a esa alerta. Si existen otras alertas o bloqueos, deben conservarse.
- **No lo reconozco:** mantener la protección y preparar el reclamo con contexto y confirmación. No aprobar una devolución automáticamente.
- **No responde:** mantener el estado y permitir retomar la revisión. No afirmar que se entregó una notificación externa; correo, SMS y push requieren canal y pruebas propios.
- **Gasto sin tarjeta asociada:** advertir y pedir revisión; no seleccionar una tarjeta arbitraria del usuario.

El bloqueo actual de tarjetas no tiene este ciclo reversible. Será necesario añadir estado, motivo, titularidad, auditoría, idempotencia y levantamiento autenticado del bloqueo preventivo. Probar alertas repetidas, reconocimiento, rechazo, ausencia de respuesta, acceso de otro titular y conservación de bloqueos preexistentes antes de habilitarlo. Los cinco usuarios manuales permanecen intactos en esta etapa.

Para el pitch, presentarlo como la siguiente validación hasta que exista evidencia de funcionamiento. El análisis histórico puntual ya implementado sirve como base, pero no equivale a este flujo completo.
