# Perfil sintético de seis meses al desplegar con Docker

`compose.yaml` configura la API para crear o sincronizar este perfil al arrancar. `compose.cloud.yaml` y `compose.voice.yaml` heredan esa configuración: no necesitan repetirla ni ejecutar un seed manual. El orden de arranque es Alembic, seed base, sincronización del perfil y finalmente Uvicorn.

## Configuración privada del despliegue

Hay dos fuentes admitidas, en este orden:

1. **`NEXQORI_DEMO_PROFILE_JSON`**: variable privada del entorno donde se ejecuta `docker compose up --build -d`. Compose la pasa a la API. Permite usar el secreto del workflow de despliegue sin transportar un archivo local.
2. **`.local/demo/profile.private.json`**: archivo privado montado de sólo lectura en `/app/demo-config/profile.private.json`. Es la alternativa ya preparada localmente.

El JSON contiene `schemaVersion: 1`, `profileId`, `name`, `email`, `document` y `password`. El manifiesto local ya contiene los valores acordados para Santiago. Debe conservarse el mismo `profileId` para actualizar esa cuenta y no crear otra. No incluir los valores privados en Git, imágenes, logs ni artefactos públicos. En Linux, el archivo y su directorio deben ser legibles por UID 10001; por ejemplo, propietario 10001:10001, archivo 0600 y directorio 0700.

Para GitHub Actions, guardar **el contenido del manifiesto local** como secreto `NEXQORI_DEMO_PROFILE_JSON` y transmitirlo al entorno que ejecuta Compose. Si Actions ejecuta Docker mediante SSH, la variable debe llegar al servidor remoto: definirla sólo en el runner no basta. La variable es de runtime; no es un build arg ni una variable VITE.

El Compose base establece `NEXQORI_DEMO_REQUIRED=true`. Si ambas fuentes faltan, el arranque falla con un mensaje genérico sin revelar credenciales; no se anuncia un despliegue sano que haya omitido este perfil. `NEXQORI_DEMO_ENABLED=false` es la exclusión explícita para instalaciones que no quieran este usuario de prueba. No es necesaria para el despliegue solicitado.

## Qué se crea y qué se sobrescribe

En una base nueva se crea el usuario con contraseña Argon2, cuatro productos y los 241 movimientos sintéticos de abril a septiembre de 2026. Crédito 4101, débito 4102, cuenta transaccional 4103 y ahorro 4104. El escenario mantiene ingreso de 40.000 MXN/mes, ahorro del 10%, pagos de internet y electricidad, mantenimiento, veinte taxis y diez restaurantes mensuales, un vuelo nacional ida/vuelta y pagos completos del crédito. No supera 41 registros/mes y conserva disponible superior al 50% del ingreso tras gastos y ahorro.

Si el perfil ya existe y su auditoría acredita que pertenece a este fixture, se sincronizan **nombre, correo, documento, contraseña, terminaciones, clasificación crédito/débito y nombres de los movimientos originales**. Los proveedores y restaurantes conservan los nombres acordados y las referencias AAAAMMDDHHmm en America/Mexico_City.

Se conservan importes, fechas, saldos, movimientos posteriores, bloqueos, reclamos y conversaciones. Sin cambios no se vuelve a generar el hash de contraseña ni una nueva auditoría. Si cambian contraseña, correo o documento, se revocan las sesiones anteriores del perfil. Los cambios se registran como `demo_profile_synchronized`.

Una identidad que corresponda a otro titular, un usuario que no tenga el marcador del fixture o un historial incompleto causan error y rollback. El proceso no elimina usuarios ni limpia PostgreSQL. La sobrescritura es de identidad y etiquetas del fixture, no un borrado de su actividad bancaria.

## Comprobación

El arranque ejecuta automáticamente:

```sh
python -m backend.six_month_demo --configured
```

Para revisar el estado inicial sin modificarlo, usando el archivo privado:

```sh
docker compose exec -T api python -m backend.six_month_demo --audit < .local/demo/profile.private.json
```

La auditoría estricta comprueba identidad/acceso, productos, fechas, nombres, montos y saldos iniciales. Si se realizaron nuevas operaciones, los saldos pueden diferir legítimamente. `--apply` conserva incluso ediciones de identidad de perfiles existentes; `--sync` sincroniza explícitamente la identidad y las etiquetas. Ambas opciones reciben el JSON por stdin; `--configured` usa la configuración de runtime y sincroniza automáticamente.

Las migraciones tienen una única cabecera `fc8319d05b74`, compatible con los cambios previos de tarjetas y compras excepcionales. Las pruebas de generación, sincronización y conservación están en `backend/tests/test_six_month_demo.py`.

## Alcance

Validación local con Docker. La publicación de rama/PR la realiza el usuario. Los datos se generan desde código versionado, pero sus accesos privados se deben suministrar al entorno de despliegue mediante una de las dos fuentes anteriores. No se consultan AWS ni el workflow remoto y no se afirma una comprobación del sitio público.
