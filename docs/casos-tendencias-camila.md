# Camila: historial y dos recorridos de atención

Los registros de este ejemplo son construidos. No representan a una persona del dataset ni prueban fraude o una falla externa. El método es una comparación estadística explicable, no un modelo de aprendizaje automático entrenado.

## Preparación compartida

Con Docker iniciado y los cinco perfiles UX creados:

```powershell
node scripts/prepare-spending-cases.mjs --confirm-local --pack=equipo-ux
```

El comando usa el manifiesto privado del paquete. Añade una sola vez los antecedentes y los dos movimientos al perfil de Camila. Repetirlo conserva la actividad posterior. El ingreso de ahorro de 7.000 MXN financia los registros construidos; sus cargos se reflejan una sola vez en la cuenta, incluidos los cargos de tarjeta asociados a esa cuenta. No se ejecuta un pago externo.

No se incluye una contraseña en este documento. Los accesos del paquete están en su guía privada local. Para otro equipo, preparar su propio paquete con `npm run test:ux:prepare` antes de ejecutar este comando.

## Recorridos

| Caso | Antecedentes | Movimiento actual | Frase para empezar | Comprobar |
|---|---|---|---|---|
| Compra fuera del patrón | Cinco compras en Mercado del Barrio: 600, 610, 590, 620 y 580 MXN; promedio 600 | Compra de 2.700 MXN completada; +350 % | «No reconozco esta compra de 2.700 pesos en Mercado del Barrio» | Consultar los antecedentes, confirmar el movimiento, revisar el relato y registrar. No prometer fraude confirmado ni devolución automática. |
| Teléfono con incidencia | Cinco recibos de 299 MXN de la misma línea | Recibo de 459 MXN y pago pendiente; +53,5 % | «Pagué mi teléfono y sigue pendiente. Además, normalmente pago 299 pesos» | Revisar estado y comprobante; preguntar qué necesita aclarar el cliente. Si cambia a importe incorrecto, recoger el importe esperado y confirmar el resumen. No afirmar recepción por el proveedor. |

En **Movimientos**, combinar búsqueda por comercio con **Comparación con el historial** y **Estado**. Abrir un movimiento para ver promedio, rango, variación y la lista de antecedentes. **Preguntar al asistente** conserva su referencia.

Se analizan páginas de 40 gastos, con opción de cargar más. La cobertura visible indica a qué conjunto se aplica el filtro. Cada comparación usa hasta seis pagos completados anteriores en 180 días; se requieren al menos tres. Marca aumentos de al menos 20 % sobre el promedio y superiores al máximo anterior. Las devoluciones aprobadas se excluyen de los antecedentes. Ingresos y cargos rechazados no son comparables. Un recibo con abonos no se compara como pago completo.

El historial de una misma referencia de servicio es más preciso que el del mismo comercio/producto/categoría. Este último no demuestra que se compraron los mismos artículos o que se mantuvo el mismo plan.

## Reinicio y voz

El control de reinicio solicitado por Bryan permanece exclusivamente en su equipo, fuera de Git. No existe un endpoint de reinicio en la API del banco. Conserva correo de notificaciones, contraseñas, tarjetas e historial. Sólo limpia la gestión creada para estos dos movimientos y restaura sus abonos de devolución cuando no tienen actividad propia. Hace un respaldo antes de cambiar la base.

La voz utiliza el mismo flujo del chat cuando el proveedor permite la sesión. La última verificación de acceso a `gpt-live-1` devolvió 404; no se presenta una llamada como validada. Mientras se resuelve, estas mismas frases permiten ensayar por texto. Las cifras bancarias permanecen en pantalla y no se envían al proveedor de voz. Ver [voz-gpt-live.md](voz-gpt-live.md).

## Verificación repetible

```powershell
.venv-app/Scripts/python.exe -m pytest backend/tests/test_spending.py backend/tests/test_payment_history.py -q
npm run build
node scripts/nexqori-spending.mjs
```

El recorrido visual usa SQLite y un usuario aislado; comprueba ES/EN/PT, filtros combinados, detalle móvil, comprobante y ausencia de cambios financieros. No altera al perfil manual de Camila. El reinicio privado se prueba aparte y no se distribuye en este repositorio.
