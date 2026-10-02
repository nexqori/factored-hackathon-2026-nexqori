# Panel de reclamos y trazabilidad por usuario

Banco local: [Panel de reclamos](http://localhost:5180/admin/complaints). El editor sigue disponible en [Flujos de atención](http://localhost:5190/?view=flows&mode=editor&lang=es).

## Cómo revisar un caso

1. Inicia sesión en el banco con un perfil administrador.
2. En Administración, busca al cliente en Usuarios y pulsa **Ver reclamos**. También puedes abrir **Panel de reclamos** desde la navegación.
3. Filtra por usuario, folio, movimiento, ID de operación o estado.
4. Selecciona el caso. El enlace conserva el usuario y el folio al recargar.
5. Revisa **Qué está pasando** y la siguiente acción. El detalle incluye el relato, los registros bancarios actuales y el resultado de una devolución, si existe.
6. Abre una conversación vinculada para leer sus mensajes en el idioma original. La consulta administrativa queda auditada.
7. En **Qué ocurrió y quién actuó**, revisa cada actividad, su fecha/hora, actor, efecto registrado y referencias de auditoría. Carga actividad anterior cuando haya más de 50 eventos.
8. Usa **Gestionar solicitud** para abrir las acciones existentes. La revisión y las decisiones conservan su confirmación, permisos y reautenticación. Elegir un caso no ejecuta esas acciones.

**Detalle del caso** muestra la información legible. **JSON · detalle técnico** muestra la misma respuesta estructurada cargada. **Actualizar** vuelve a consultar el banco; no hay sondeo automático. El cliente tiene su propio detalle en **Mis solicitudes**, limitado al titular de la sesión.

## Qué significa cada dato

| Dato | Procedencia y límite |
| --- | --- |
| Relato del cliente | Texto guardado en la solicitud. No demuestra por sí mismo un cargo incorrecto. |
| Movimiento y producto | Referencia explícita de la solicitud y mismo titular. Importe con signo, moneda, estado, fecha y terminación del producto. Sin PAN ni CVV. |
| Devolución | Operación persistente RF, estado, cuenta enmascarada, motivo, administrador, fecha y referencia CR del abono cuando existe. |
| Conversación | Mismo titular y vínculo por folio de auditoría o por movimiento. Una conversación del mismo movimiento puede tratar asuntos adicionales; no se atribuye automáticamente todo su texto al reclamo. |
| Actividad | Eventos del folio, del movimiento, de las conversaciones vinculadas y bloqueo del producto asociado. La interfaz identifica la relación. Un bloqueo del producto no prueba la causa del reclamo. |
| Siguiente acción | Orientación derivada del estado guardado. No representa una tarea asignada, una decisión de un modelo ni una operación ejecutada. |

Los datos bancarios son una lectura **actual**. El registro de que una herramienta consultó un movimiento no conserva una copia histórica de todos los valores que leyó. Las fechas se muestran en la zona horaria del navegador. La devolución y el reclamo conservan estados separados: aprobar un abono no cierra automáticamente el caso.

Los chats generales sin referencia no se enlazan por coincidencia de texto; administración puede consultarlos en Auditoría. Las ejecuciones y mensajes privados del editor de flujos siguen en su almacén local. Este panel muestra las lecturas bancarias que dejaron auditoría, pero no importa automáticamente las trazas de Jev/Luna ni crea un reclamo al ejecutar el editor. Tampoco conecta logs de procesadores externos o de fallos de la app.

## API y autorización

- `GET /api/requests/{request_id}/trace`: cliente autenticado, sólo un folio propio.
- `GET /api/admin/users/{user_id}/requests/{request_id}/trace`: administrador autenticado; folio y titular deben coincidir.
- `before`: cursor del último evento de la página. El servidor rechaza cursores ajenos al caso y conserva un orden estable por fecha/ID.
- `conversationOffset`: páginas de 20 conversaciones. Los mensajes usan las rutas existentes con páginas de 50.

Cada lectura válida registra `claim_trace_viewed`, con titular, lector, folio y fecha. La API devuelve campos permitidos; omite secretos, documento de identidad, claves de idempotencia y datos completos de tarjeta. No hay migraciones ni cambios en el esquema para este panel. La auditoría sigue siendo local y no es inmutable.

## Prueba repetible

Con Docker iniciado:

```powershell
npm run docker:up
npm run test:claims
```

La prueba crea tres clientes y un administrador nuevos de **verificación**. Prepara tres estados mediante la API real de PostgreSQL: devolución pendiente, devolución aprobada y atención humana solicitada. No modifica casos ni saldos previos. Después recorre las pantallas ES/EN/PT, historial, JSON, acceso desde Usuarios, móvil, error de lectura y aislamiento. Compara productos, movimientos y solicitudes antes/después de consultar el panel; leerlo sólo debe añadir auditoría.

Los datos preparados son persistentes. Los accesos, enlaces y capturas se guardan en `.local/verification/claims/{runId}/`. La ruta del último conjunto está en `.local/verification/claims/latest.json`; `INICIAR.private.md` contiene contraseñas locales y no se publica. Cada repetición prepara un conjunto nuevo. No llama a modelos ni captura audio.

Validación de servidor: `python -m pytest backend/tests/test_claim_trace.py -q`. Para regresión se mantienen los comandos de `AGENTS.md`, incluido `npm run test:ui` y `npm run test:experience`.
