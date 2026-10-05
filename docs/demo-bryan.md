# Perfil de Bryan para el pitch

Reutiliza los casos sintéticos de [Camila](casos-tendencias-camila.md) y sus
[condiciones del servicio](condiciones-servicio-camila.md) en un perfil independiente.
Todos los importes son pesos mexicanos (MXN). No convierte monedas ni copia
conversaciones, reclamos, credenciales o destinatarios de correo de otro usuario.

Con la API actualizada y Docker iniciado:

```powershell
node scripts/prepare-bryan-demo.mjs --confirm-local
node scripts/demo-access.mjs --confirm-local
```

Los dos accesos verificados (Bryan y administración) quedan en `.local/ux-users/bryan-demo/ACCESOS.private.md`. El exportador no cambia las contraseñas.

El acceso, contraseña generada y mensajes de prueba quedan en
`.local/ux-users/bryan-demo/INICIAR.private.md`, excluido de Git. El comando crea
un solo usuario llamado Bryan, cuenta, ahorro, tarjeta e historial. La inserción
es atómica y auditada. Repetirlo recupera el mismo perfil y conserva su actividad;
no es un comando de reinicio.

| Caso | Historial | Movimiento a revisar |
| --- | --- | --- |
| Teléfono fuera del plan | Cinco pagos de 299 MXN; condiciones de ejemplo de 299 MXN/mes | 459 MXN pendientes; diferencia de 160 MXN |
| Compra fuera de tendencia | Cinco compras con promedio de 600 MXN | Compra completada de 2.700 MXN |

El cliente identifica y confirma el movimiento. Nexi reúne la evidencia y permite
revisar el resumen antes de registrar el reclamo. El administrador decide sobre
una solicitud de devolución de un cargo completado. Un importe fuera de tendencia
no prueba fraude; un pago pendiente requiere investigación y no se devuelve ni
anula automáticamente. El perfil comienza sin reclamos y permite ensayar el
recorrido completo desde el cliente.

Las condiciones, importes e identidad son construidos para la demo, no registros
reales del dataset. El correo de acceso es ficticio; las notificaciones requieren
un destinatario configurado y verificado por el usuario.
