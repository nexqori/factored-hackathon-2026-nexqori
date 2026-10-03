# Base técnica de Nexqori

React + TypeScript + Vite presenta la UI; react-i18next mantiene ES/EN/PT. FastAPI valida y autoriza. PostgreSQL conserva usuarios, sesiones, productos, movimientos, solicitudes, eventos, conversaciones y mensajes. SQLAlchemy y Alembic mantienen modelo y migraciones. Docker Compose une db, api y web mediante un único origen local.

El acceso admite correo o documento y contraseña, con límite de intentos compartido por cuenta. Tamaño de letra e idioma se guardan en el perfil. Cada mensaje pertenece a una conversación del mismo titular mediante FK compuesta; abrir una conversación es una elección explícita.

La voz está fuera del alcance actual; se añadirá en otra implementación. La base conserva el asistente escrito, sin motores de audio ni endpoints de voz.

Las contraseñas tienen hash Argon2. La cookie HttpOnly lleva una sesión opaca; su hash se guarda en servidor, con caducidad y revocación. Las mutaciones verifican origen, CSRF, esquema y permisos. La titularidad se filtra en consultas y se refuerza con claves foráneas compuestas. Importes en unidades menores enteras; no usar float para operaciones monetarias. Los secretos van en `.env`, excluido de Git.

El contrato de `backend/navigation.py` contiene destinos de cliente: home, products, movements, requests, services, help, accounts, cards, transfers, payments, loans, investments, insurance, cash y settings. `src/navigation.ts` vuelve a validar herramienta, destino y ruta antes de navegar. No hay destino administrativo ni redirección externa. La API registra la solicitud de navegación; ese evento no prueba que el navegador terminó de abrir la pantalla.

La versión base usa clasificación por reglas y respuestas localizadas. Para conectar después un modelo, usar un adaptador en servidor, validar sus herramientas con el mismo esquema, aplicar permisos desde la sesión y registrar resultado/error. Nunca tomar identidad, permisos, confirmación o saldo del texto del modelo. La confirmación de una gestión se recibe desde la UI y su API específica, no del chat.

El dataset sirve para decisiones agregadas. No importar relaciones caso–producto o evento–producto a una sesión de cliente: fueron inconsistentes. El seed de la app usa fixtures ficticios con titularidad coherente.

Documentar las limitaciones técnicas sin etiquetas repetitivas en la interfaz: sin banco real, sin ejecución monetaria, sin LLM ni operador humano conectados. Autenticación local no equivale a una plataforma bancaria lista para producción. TLS, MFA, recuperación de cuentas, límites distribuidos, integración bancaria, observabilidad y revisión operativa necesitan trabajo específico antes de otro entorno.

Catálogo: `backend/service_catalog.json`, compartido por API y cliente. Búsqueda por necesidad/proveedor y categorías, con formularios para facturas, transferencias, consultas y reclamos. Los comercios provienen de agregados del dataset; los convenios de recaudación no están acreditados. `POST /api/services/{id}/requests` valida cuenta propia, referencia, importes enteros, confirmación e idempotencia; guarda servicio y detalle sin debitar saldo. La cuenta de origen tiene FK compuesta de titular. El agente puede abrir sólo IDs registrados; jamás ejecutar el envío.
