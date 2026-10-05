# Demo en AWS con Docker Compose y HTTPS

Configuración para una instancia EC2 Linux con Docker Engine, Compose v2 y Node.js 24 para preparar los accesos. `compose.cloud.yaml` añade Caddy delante de la aplicación y fija el origen permitido y la cookie Secure. El banco conserva una sola API y PostgreSQL persistente. Este documento prepara el despliegue; no acredita que exista una instancia ni un certificado emitido.

## Dominio y acceso

1. Asigna una dirección pública estable al servidor y apunta el registro DNS A de tu subdominio a ella. Usa AAAA sólo si también configuraste IPv6.
2. En el grupo de seguridad de EC2, permite TCP 80 y 443 al público. Limita SSH a la IP del administrador o usa el acceso administrado que tenga el equipo. No publiques 5180, 8000 ni 5432.
3. Conserva acceso saliente para imágenes Docker, certificados, proveedores de IA y SMTP. El navegador también debe poder conectar con el proveedor de voz.

Caddy obtiene y renueva el certificado y redirige HTTP a HTTPS cuando DNS y puertos están disponibles. Sus certificados se conservan en `caddy_data`. Referencias: [HTTPS automático de Caddy](https://caddyserver.com/docs/automatic-https) y [grupos de seguridad de EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html).

## Preparar el servidor

Desde el checkout del repositorio:

```sh
git switch main
git pull --ff-only
node scripts/setup-local.mjs
mkdir -p .local/intent-lab .local/provider-updates
chmod 700 .local
```

Edita el `.env` privado creado por setup y añade `PUBLIC_DOMAIN=tu-subdominio.tu-dominio.com`, sin `https://`, puerto ni ruta. Conserva sus contraseñas aleatorias. El override cloud deriva `APP_ORIGINS=https://...` y fuerza `COOKIE_SECURE=true`, aunque los valores locales del archivo sean distintos.

Configura los proveedores y el flujo en `.local/intent-lab/` según [la guía del agente](agente.md) y [la guía de voz](voz-gpt-live.md). Configura Gmail/SMTP en `.local/notifications.env` según [notificaciones](notificaciones-gmail.md). No copies automáticamente toda la carpeta privada del equipo: incluye sólo la configuración necesaria para esta instalación. API keys y claves SMTP permanecen fuera de Git.

La API se ejecuta con UID 10001. En Linux, permite a ese usuario leer los archivos de configuración y escribir en `.local/provider-updates`; este último directorio conserva el estado de proveedores de ejemplo. Los archivos de entorno los lee Compose. Evita permisos globales de escritura. Si el directorio de ejemplos acaba de crearse:

```sh
sudo chown 10001:10001 .local/provider-updates
chmod 750 .local/provider-updates
```

Los datos locales no están en GitHub. En una base nueva el seed crea sólo los usuarios iniciales. Para reconstruir los escenarios compartidos, usa [usuarios de prueba](usuarios-prueba-ux.md) y [Bryan](demo-bryan.md). Transferir una base existente requiere un respaldo privado, conservando las claves de base y usuarios que correspondan; generar otro `.env` no cambia las claves ya persistidas.

## Arrancar

Demo con voz:

```sh
docker compose -f compose.yaml -f compose.voice.yaml -f compose.cloud.yaml config --quiet
docker compose -f compose.yaml -f compose.voice.yaml -f compose.cloud.yaml up --build -d
```

Demo sólo texto: omite `-f compose.voice.yaml` en ambos comandos. Conserva siempre `compose.cloud.yaml` al final. La misma combinación debe usarse en futuras actualizaciones; omitir voz la desactiva y omitir cloud pierde la configuración HTTPS del banco.

La API aplica Alembic y el seed idempotente antes de aceptar tráfico. Mantén una sola réplica/worker: llamadas y límites de acceso usan memoria del proceso. El editor LAB no se publica con este Compose.

## Comprobar la demo

```sh
docker compose -f compose.yaml -f compose.voice.yaml -f compose.cloud.yaml ps
curl -I "http://$PUBLIC_DOMAIN/"
curl --fail "https://$PUBLIC_DOMAIN/api/health"
```

En estos comandos de shell, exporta `PUBLIC_DOMAIN` o sustituye su valor; Compose lo lee del `.env`, pero el shell no lo exporta automáticamente.

Comprueba el certificado sin omitir la verificación TLS, la redirección HTTP y un login en HTTPS. En el navegador, verifica cookie Secure/HttpOnly, logout y un cliente sin acceso a otro titular. Prueba un reclamo con movimiento, revisión administrativa y PDF en Mis documentos. Para voz, concede micrófono y prueba inicio, navegación y cierre; la prueba de audio real puede generar consumo del proveedor. El código por correo requiere SMTP configurado en esta instalación.

## Actualizar y recuperar

Antes de actualizar, termina las llamadas y guarda un respaldo privado de PostgreSQL. Ejemplo para un shell Linux, desde el servidor:

```sh
mkdir -p .local/backups
docker compose exec -T db pg_dump -U postgres -d nexqori -Fc > .local/backups/nexqori.dump
```

Guarda también la revisión Git desplegada, la configuración privada y los volúmenes Caddy. `caddy:2-alpine` recibe correcciones de la serie 2; registra el digest utilizado para reproducir una entrega. Para una actualización, descarga la revisión verificada y repite el comando `up --build -d` con los mismos archivos. Revisa salud antes de reabrir las pruebas.

Una reversión de código debe ser compatible con la migración aplicada. Si no lo es, restaura el respaldo en una base nueva y valida antes de cambiar el destino. No uses `down -v` para reiniciar: elimina la base y los certificados. Conserva respaldos fuera de la instancia y prueba su restauración.

Esta entrega es una demo bancaria con operaciones locales y datos ficticios. El despliegue público, el certificado y los proveedores deben comprobarse en el servidor de destino; las pruebas locales no sustituyen esa comprobación.

## Perfil sintético de seis meses

La carga optativa del historial y sus cuatro productos está documentada en [perfil de seis meses](perfil-seis-meses-despliegue.md). El arranque de la API usa el manifiesto privado `.local/demo/profile.private.json` cuando está instalado en el servidor; no está contenido en Git. El workflow que despliega debe conservarlo o provisionarlo antes de recrear la API y comprobar el perfil por HTTPS después. Abrir un PR no verifica por sí solo ni el despliegue ni la carga de datos.
