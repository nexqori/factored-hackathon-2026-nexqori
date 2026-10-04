# Correo de notificaciones y bloqueo confirmado

El remitente de Gmail pertenece a la configuración del servidor. Cada cliente elige su propio destinatario en **Configuración → Correo de notificaciones**. Puede usar una dirección distinta de su correo de acceso; debe verificar que la controla.

## Configurar Gmail localmente

1. Activa la verificación en dos pasos de la cuenta remitente y crea una contraseña de aplicación, si la cuenta lo permite. No uses la contraseña habitual ni una clave de OpenAI. [Guía oficial de Google](https://support.google.com/accounts/answer/185833?hl=es).
2. Crea o edita `.local/notifications.env`, que está excluido de Git, con este formato. Sustituye sólo el correo y la contraseña; escribe la contraseña de aplicación sin los espacios visuales.

```dotenv
MAIL_SMTP_HOST=smtp.gmail.com
MAIL_SMTP_PORT=587
MAIL_SMTP_SECURITY=starttls
MAIL_SMTP_USER=tu-cuenta@gmail.com
MAIL_SMTP_PASSWORD=contraseña-de-aplicación
```

3. Ejecuta `docker compose up -d --force-recreate api web` después de guardar. No uses `docker compose config` para compartir la configuración: puede mostrar secretos resueltos.
4. Inicia sesión como el cliente de la prueba y abre Configuración. Escribe el destinatario deseado y tu contraseña de Nexqori. Solicita el código y escríbelo en el formulario. El correo de acceso no cambia.
5. En **Tarjetas → Bloquear tarjeta**, confirma tu contraseña de Nexqori, solicita el código, revisa la terminación de la tarjeta en el correo y confirma el bloqueo con el código recibido.

SMTP usa `smtp.gmail.com:587` con STARTTLS y validación de certificado. También admite SSL en 465. [Configuración oficial de Gmail](https://support.google.com/mail/answer/7104828?hl=es). Algunas cuentas administradas no permiten contraseñas de aplicación; se debe comprobar esa disponibilidad en la cuenta remitente.

`MAIL_FROM` es opcional: por defecto se usa `MAIL_SMTP_USER`. No se almacena la credencial en PostgreSQL, el frontend ni los archivos compartidos del equipo.

## Comportamiento y límites

- Código de seis dígitos válido cinco minutos, con cinco intentos. Un minuto mínimo entre envíos y máximo diez códigos por titular en una hora. Reenvío invalida el código anterior del mismo propósito/tarjeta.
- Código ligado a titular, sesión, propósito y tarjeta. Un código de verificación de correo no bloquea una tarjeta. Cerrar sesión impide usarlo desde otra sesión.
- Cambiar el correo verificado invalida los códigos de bloqueo pendientes. Los códigos se guardan con Argon2; no se devuelven por API, se escriben en auditoría ni se envían al modelo.
- Solicitar el código no bloquea la tarjeta. El bloqueo requiere confirmación; no toca saldo ni movimientos. Un reintento de una operación ya completada no crea un segundo bloqueo.
- Compose exige confirmación por correo. Si Gmail no está configurado, el envío falla o falta verificar el destinatario, no hay bloqueo nuevo ni confirmación de envío inventada. Durante el pitch hay que preparar el correo antes del recorrido.
- El bloqueo afecta al estado local de Nexqori; no está conectado a una red emisora. El ciclo de protección automática por gasto anómalo y desbloqueo posterior sigue siendo un frente separado.
- Los correos implementados son verificación de destinatario y código de bloqueo. No hay campañas, notificaciones de todos los movimientos ni cola de entrega/reintentos. SMTP aceptado no prueba recepción en la bandeja; comprueba también spam.
- No existe recuperación del segundo factor ni canal alternativo si el titular pierde el correo. No presentar este prototipo como protección bancaria de producción.

## Pruebas

```powershell
.venv-app/Scripts/python.exe -m pytest backend/tests/test_notifications.py -q
npm run test:notifications
```

La prueba UI usa un buzón controlado en un servidor aislado :5194, sin Gmail, micrófono, modelos ni usuarios manuales. Sus endpoints de prueba no están registrados por la aplicación desplegada. `BANK_CARD_BLOCK_EMAIL_REQUIRED=false` se reserva a pruebas históricas aisladas; Compose fija `true`.
