> Decisiones vigentes, 2026-09-28: producto **Nexqori**, P11 Terracota suave, **React + FastAPI + PostgreSQL**, Docker local y **ES/EN/PT** en toda la base. La navegación guiada ya forma parte del aplicativo; un LLM y las operaciones bancarias reales requieren integración posterior. El alcance implementado y verificado se describe en README.md y ESTADO.md. Los gráficos y propuestas siguientes son contexto, no prueba de implementación.

# Objetivo de la aplicación bancaria

Fecha: 2026-09-28, America/Lima (UTC-05:00).
Fuente: cuatro gráficos aportados por Bryan el 28 de septiembre. Propuesta de producto; no equivale a implementación ni a alcance validado del hackathon.

## Objetivo vigente

Construir una aplicación bancaria con un asistente multiservicios en español y portugués que ayude a consultar información, navegar hacia una operación, realizar gestiones e investigar reclamos, mediante texto y voz. Debe conservar contexto, verificar evidencia y permisos antes de actuar, confirmar resultados y transferir a una persona cuando corresponda. El diseño busca confianza y facilidad de uso para personas con distintos niveles de experiencia digital, incluidos adultos mayores.

Bryan prevé comenzar por la aplicación de usuario. Antes se preparan nombre y paleta para votación; todavía no se inicia desarrollo.

## Alcance representado en los gráficos

- **Panel de usuario:** conversación por texto/voz; experiencia simple; alternativa de atención por agente. Los gráficos segmentan por edad y experiencia bancaria. Recomendación pendiente: permitir elegir o cambiar la modalidad, sin imponerla por edad ni inferir capacidad por acento.
- **Reclamos:** movimiento no reconocido, importe cuestionado, pago dudoso/error al pagar y seguimiento de reclamo. Consultar contexto e historial, reunir evidencia, validar permisos, derivar con contexto, entregar seguimiento y medir satisfacción.
- **Consultas:** productos y operaciones, ayuda de uso, campañas, histórico de transacciones con analítica y visualizaciones, solicitudes y envío de información en PDF por correo/WhatsApp cuando el usuario lo autorice.
- **Navegación:** identificar intención, consultar un mapa de pantallas autorizadas y llevar al usuario al producto u operación pertinente.
- **Acciones:** problema, contexto, validaciones y permisos alimentan herramientas API/MCP; registrar y verificar el resultado.
- **Panel administrativo:** acceso, gestión y asignación de usuarios; alcance concreto de roles por definir.
- **Medición:** comparar alternativas de clasificación de intención/problema/suficiencia de evidencia; medir tiempos de acción y satisfacción. Los rótulos LLM/JEV/NLP del gráfico son alternativas por aclarar, no tecnologías aprobadas.
- **Bases:** español y portugués, persistencia de conversaciones y auditoría de acciones. Política de acceso, retención y tratamiento de esos registros pendiente. Gamificación aparece como idea, sin reglas definidas.

## Ajustes de flujo por resolver

- La petición de datos/evidencias debe volver a la investigación y evaluación de suficiencia antes de concluir.
- Contrastar con históricos ayuda a investigar un cobro, pero no demuestra que sea correcto: se necesitan condiciones aplicables verificadas.
- Separar solicitud enviada, recibida, ejecutada y resuelta; confirmar el estado real del servicio.
- La cobertura textual del dataset no sostiene entrenamiento directo de temas de queja: los textos repetitivos y relaciones incoherentes están documentados en el EDA.
- Especificar un recorrido profundo para evaluación y demo. La amplitud visual de la app no implica implementar todos los servicios del banco.

## Gráficos de referencia

1. [Panel de usuario](documentos/diseno-2026-09-28/01-panel-usuario.png).
2. [Clasificación y componentes](documentos/diseno-2026-09-28/02-clasificacion-componentes.png).
3. [Ideas y bases](documentos/diseno-2026-09-28/03-ideas-bases.png).
4. [Navegación, acciones y aplicaciones](documentos/diseno-2026-09-28/04-navegacion-aplicaciones.png).

## Decisiones pendientes

- Nombre y paleta, por votación: [opciones de identidad](IDENTIDAD-PARA-VOTAR.md).
- Pantallas y recorrido de la primera versión del panel de usuario.
- Roles, políticas de demo y contratos de herramientas.
- Casos reservados de evaluación en ambos idiomas y comparación con un flujo base.

No se ha creado repositorio remoto, implementado la aplicación, desplegado ni enviado mensajes al equipo en este frente.
