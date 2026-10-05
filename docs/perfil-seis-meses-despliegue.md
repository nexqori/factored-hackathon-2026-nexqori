# Perfil sintético de seis meses en el despliegue

Este perfil es optativo. El código versionado genera cuatro productos y 241 movimientos sintéticos de abril a septiembre de 2026, sin copiar bases ni registros de otros titulares. La identidad y contraseña llegan mediante un manifiesto privado; no se incluyen en Git ni en la imagen Docker.

## Qué conserva el escenario

- Tarjeta de crédito 4101, débito 4102, cuenta transaccional 4103 y ahorro 4104.
- Ingreso de 40.000 MXN por mes, ahorro del 10%, internet y electricidad por crédito, mantenimiento por débito, diez taxis por cada tarjeta y diez restaurantes mensuales.
- Un vuelo nacional de ida y vuelta, compras adicionales y liquidación mensual del crédito. Máximo 41 registros al mes; disponible tras gastos y ahorro superior a la mitad del ingreso.
- Restaurantes con nombres propios y proveedores Fibra Aurora / Energia Luminara. Las referencias de los consumos llevan AAAAMMDDHHmm en America/Mexico_City, coincidiendo con la interfaz.
- Etiquetas de crédito/débito persistentes y traducidas ES/EN/PT.

## Archivo privado necesario

El archivo del servidor es `.local/demo/profile.private.json`. Su estructura es:

```json
{
  "schemaVersion": 1,
  "profileId": "identificador-estable-del-perfil",
  "name": "Nombre del titular",
  "email": "correo-del-titular@example.com",
  "document": "DOCUMENTO-DE-PRUEBA",
  "password": "CONTRASENA-PRIVADA-DEL-TITULAR"
}
```

Estos son marcadores, no accesos utilizables. Para el caso ya preparado se debe transferir exclusivamente el archivo privado existente en el equipo, conservando su `profileId`, nombre, correo, documento y contraseña. No generar una identidad distinta. No subir el archivo a la rama, a un PR, a logs ni a un artefacto público.

En Linux, el contenedor de la API usa UID 10001. El directorio del servidor debe permitirle lectura y recorrido; el archivo puede tener propietario 10001:10001 y modo 0600, con directorio 0700. Debe ser legible en `/app/demo-config/profile.private.json`; Compose lo monta en modo de solo lectura. No necesita acceso del navegador ni variables VITE.

## Integración con el despliegue existente

1. Aprobar y fusionar el PR en la rama que despliega el workflow existente. Publicar la rama o abrir el PR por sí solo no confirma el despliegue.
2. Antes del primer arranque de esta revisión, entregar el manifiesto de forma privada al servidor. Si el workflow usa un secreto de GitHub Actions, el secreto debe llegar al **servidor de ejecución**, no quedarse sólo en el runner. No imprimirlo ni ejecutar shell tracing. Un proceso que recrea el checkout debe conservar este archivo junto con el resto de `.local`.
3. Reconstruir API y web con los mismos archivos Compose que ya usa el despliegue (conservar `compose.cloud.yaml` y la opción de voz vigente). No iniciar un segundo despliegue concurrente.
4. El arranque aplica Alembic, el seed existente y `python -m backend.six_month_demo --configured` antes de iniciar Uvicorn. Si el archivo existe, crea el perfil atómicamente; en los siguientes arranques conserva contraseñas, nombres editados, saldos y actividad. Si falta, la carga es optativa y no se crea el perfil. Para exigirlo en el workflow, comprobar que el archivo existe y ejecutar la auditoría de aceptación.
5. Si hay una colisión de correo/documento o un perfil parcial, aborta la carga sin sobrescribir a otro titular. Investigar el caso antes de reintentar; no vaciar la base.

La migración de unión `fc8319d05b74` permite actualizar desde `fb7218c04a63` (tipos de tarjeta) y desde `fb7208ea46c3` (compras excepcionales), sin cambiar revisiones ya aplicadas.

## Verificación del servidor después de desplegar

Desde el checkout del servidor, con la misma combinación de archivos Compose:

```sh
docker compose exec -T api python -m backend.six_month_demo --audit < .local/demo/profile.private.json
```

`--audit` es una comprobación estricta de aceptación inicial: identidad/acceso, fechas, nombres, montos, tipos y saldos. No modifica datos ni devuelve credenciales. Una vez que el titular hace operaciones nuevas, los saldos pueden diferir legítimamente; el arranque normal no los restablece. Verificar además por HTTPS acceso con correo y documento, ambas etiquetas, cuatro productos y 241 movimientos iniciales. Conservar la evidencia fuera de Git.

La carga manual equivalente (sólo cuando se quiera preparar explícitamente el perfil) es:

```sh
docker compose exec -T api python -m backend.six_month_demo --apply < .local/demo/profile.private.json
```

La contraseña se envía por stdin y se guarda como Argon2 en PostgreSQL. Ningún comando envía pagos externos. La generación puede probarse con `python -m pytest backend/tests/test_six_month_demo.py backend/tests/test_migrations.py -q`.

## Alcance verificado y requisito pendiente

En este checkout sólo se ha encontrado `.github/workflows/ci.yml` (Nexqori checks), que ejecuta pruebas y compilación. El usuario indica que existe despliegue automático por Actions, pero no se ha identificado su workflow ni accedido al servidor desde este equipo. Este cambio prepara la carga para ese despliegue; **no acredita que el manifiesto esté instalado en la nube ni que el sitio público ya tenga el perfil**. La publicación sólo queda comprobada después del workflow real y la verificación HTTPS descrita arriba.
