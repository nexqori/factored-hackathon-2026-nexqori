# Comparación histórica de pagos

El chat compara el movimiento seleccionado con un máximo de seis pagos anteriores del mismo titular, dentro de los 180 días previos al cobro. Muestra cantidad de antecedentes, promedio, rango y diferencia en importe y porcentaje. Funciona en español, inglés y portugués.

Cuando hay un recibo, exige el mismo servicio y referencia (por ejemplo, el mismo número telefónico). Sin recibo, compara comercio, producto y categoría; avisa que esta coincidencia no acredita la misma línea o plan. No combina monedas ni usuarios.

Sólo usa débitos completados anteriores. Excluye devoluciones aprobadas, pagos pendientes, rechazados y recibos abonados parcialmente o en varias operaciones. No convierte la suma de abonos en un recibo completo. La media usa los importes en centavos y redondea medio centavo hacia arriba; el porcentaje se calcula con la media sin redondear.

Si el cargo seleccionado supera el total de su recibo vinculado, señala esa discrepancia directamente y suspende la comparación con otros recibos. No lo describe como un abono parcial.

Con al menos tres antecedentes, señala un aumento que supera tanto el máximo observado como el promedio en un 20 % o más. Es una regla inicial de revisión, no una regla bancaria, una probabilidad estadística ni prueba de un cobro incorrecto. Con uno o dos antecedentes muestra la diferencia y advierte que falta historial. Sin antecedentes lo indica expresamente. Los pagos pueden ser irregulares: no los presenta como una mensualidad fija.

El bot pide aclarar un cambio de plan o cargo adicional si detecta ese aumento. Conserva la pregunta sobre el importe esperado: el promedio no acredita lo contratado. Registrar el reclamo aún requiere revisar y confirmar; una devolución conserva la aprobación del administrador.

La comparación reutiliza la lectura autenticada y auditada de evidencias del movimiento. Los importes y registros enriquecen la respuesta en servidor y no se incorporan al historial enviado a los modelos. No modifica saldos ni crea movimientos. Las pruebas usan historiales ficticios aislados; no agregan pagos a los usuarios manuales.

Validación repetible:

```powershell
.venv-app/Scripts/python.exe -m pytest backend/tests/test_payment_history.py -q
npm run test:chat:flow
```

El primer comando verifica límites, referencia, titular, abonos, redondeo, ausencia de mutaciones y exclusión de datos bancarios del modelo. El segundo recorre el chat y el registro de reclamos en ES/EN/PT con proveedores controlados, sin llamadas externas.
