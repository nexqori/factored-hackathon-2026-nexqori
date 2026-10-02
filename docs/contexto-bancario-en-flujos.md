# Probar flujos con registros del usuario del banco

Actualización del 2 de octubre: [chat conectado al banco, pago de teléfono con comprobante y sección Mis reclamos](chat-bancario-y-pagos.md). Esta ampliación sustituye las limitaciones anteriores que indicaban que el chat sólo navegaba y que teléfono sólo registraba solicitudes. Los demás servicios conservan su alcance.

El bloque **Reunir contexto del caso** puede consultar movimientos, solicitudes vinculadas, tarjetas enmascaradas y eventos internos del titular autenticado. Se conserva un solo flujo: **Consulta o problema · Jev** clasifica y deriva directamente; los problemas pasan a identificar el caso, cargar su contrato y reunir contexto.

## Empezar

1. Inicia Docker y el LAB según [INICIO-EQUIPO](../INICIO-EQUIPO.md) y el [README del LAB](../experiments/intent-lab/README.md).
2. Abre el [banco](http://localhost:5180/) e inicia sesión como cliente. Usa el mismo navegador y hostname para el [editor](http://localhost:5190/?view=flows&mode=editor&lang=es); no mezcles `localhost` con `127.0.0.1`.
3. En **Inicio → Registros del banco**, pulsa **Consultar mis registros**. Aparecen el titular y hasta veinte movimientos recientes de esa cuenta. Selecciona el movimiento. Si la ejecución anterior empezó sin conexión bancaria, usa primero **Nueva conversación**. El folio es opcional: si ya existe una solicitud vinculada, el servidor la recupera automáticamente. Un folio manual distinto del que corresponde al movimiento se rechaza.
4. Escribe el problema y pulsa **Paso a paso** o **Flujo completo**. Jev decide la familia y el caso; la referencia seleccionada no fuerza la clasificación. Al ejecutar Contexto, la API del banco comprueba titularidad y registra las consultas en auditoría.
5. Selecciona el bloque Contexto. **Resultado** muestra datos declarados, datos consultados, fuentes, folios de auditoría, preguntas y siguiente paso. **JSON · detalle** conserva la salida completa. El botón de ampliar permite pasar de un panel de 500 a 690 píxeles en escritorio.
6. Si falta información, **Responder y aportar datos** abre la conversación. Si falta el movimiento, elígelo en Registros del banco y continúa; no hace falta inventar un mensaje. Las respuestas vuelven a Contexto sin repetir Jev. Las instrucciones y referencias adicionales se editan en **Parámetros**; cambiar reglas durante una ejecución requiere restaurarlas o empezar una conversación nueva.

Seleccionar o recargar conserva el último resultado y no repite consultas. Sólo **▶** vuelve a ejecutar el bloque, con sus entradas guardadas. Cada ejecución vinculada al banco exige una sesión vigente del mismo titular para consultarla, continuarla, repetirla o descargar su registro mediante la API. El historial general del LAB excluye esas ejecuciones; conserva el enlace con `execution` para recuperarlas. Cerrar la sesión bancaria impide acceder nuevamente hasta autenticarse.

## Tres casos preparados

Los registros de prueba son fixtures persistentes y coherentes en PostgreSQL, basados en las familias del EDA. **No son una importación de clientes del dataset ni transcripciones auténticas.** Elegir un ejemplo del catálogo tampoco atribuye registros del dataset a la cuenta autenticada.

```powershell
npm run test:cases:prepare
```

El comando crea tres clientes nuevos sin reemplazar cuentas existentes. Los accesos y movimientos quedan en el archivo local privado indicado por `.local/verification/cases/latest-manual.json`, junto a `INICIAR.private.md`. No publicar estos archivos.

| Cliente / caso | Registro disponible | Qué revisar en Contexto |
| --- | --- | --- |
| Bloqueo / cargo no reconocido | Cargo completado de 185 MXN | Movimiento, fecha e importe provienen del banco. La protección y devolución son propuestas pendientes de validación. |
| Devolución / cobro incorrecto | Cargo completado de 459,90 MXN | Obtiene el cargo del banco; pide el importe esperado o la diferencia si el cliente aún no lo declaró. |
| Derivación / pago pendiente | Movimiento pendiente de 129,90 MXN | Obtiene estado y fecha sin pedir que se repita el pago. No afirma que el pago terminó ni que se entregó una derivación. |

Los cargos se almacenan con importe negativo; la vista formatea la moneda conservando ese signo. El cliente puede describir el importe positivo de la compra. Ambas fuentes permanecen separadas: la extracción no decide por sí sola que coincidan ni que proceda una devolución.

## Prueba automática repetible

Con el banco en 5180, puerto 5191 libre y el paquete anterior preparado:

```powershell
npm run build:lab
npm run test:lab:bank
```

El script usa React y FastAPI reales y las sesiones/lecturas de PostgreSQL del banco local. Ejecuta los tres casos en ES/EN/PT con respuestas **controladas** de Jev/Luna: no consume claves ni mide calidad de clasificación. Comprueba datos faltantes, selección del movimiento durante una pausa, resumen/JSON, ampliación, recarga, aislamiento de titulares y accesibilidad escritorio/móvil. Verifica las referencias de auditoría directamente en PostgreSQL y que productos, movimientos y solicitudes permanezcan intactos. Los resultados y capturas se guardan en `.local/intent-lab/verification/bank-context-ui.json` y archivos vecinos.

Para evaluar los proveedores reales, usa los mensajes del archivo privado en el editor 5190 con la configuración local existente. Las pruebas controladas no representan un benchmark de Jev o Luna.

## Límites y trazabilidad

- La conexión usa la cookie HttpOnly de la sesión bancaria por el prefijo `/api/lab-api/editor`; el navegador no lee el token. El adaptador sólo puede llamar a `/api/session` y al gateway cerrado `/api/assistant/tools/read` en el banco local. No modifica la política de origen/CSRF del banco ni acepta URLs, SQL, roles o titulares elegidos por el modelo.
- La identidad se valida en cada petición vinculada y cada herramienta vuelve a comprobar su referencia. Los checkpoints locales contienen titular, referencias, resultados y auditoría; **no contienen cookie ni CSRF**. Las respuestas bancarias se combinan después de la extracción del cliente y no se envían a Jev/Luna.
- `observations` son citas declaradas; `verified_facts` son campos obtenidos de registros internos, con fuente, referencia, hora e ID de auditoría. Eso acredita la lectura del registro, no la legitimidad del cargo ni la elegibilidad de una devolución.
- `executed_tools` identifica lecturas realizadas; `executed_operations` permanece vacío. Si falla una lectura, Contexto se detiene y conserva los IDs de las consultas ya realizadas. No reemplaza la evidencia con una respuesta del modelo.
- Los eventos proceden de movimientos/solicitudes de Nexqori, hasta veinte por movimiento. **No son logs técnicos de caídas de la app ni registros de un procesador externo.** La comprobación local de incidencias sigue siendo otra plantilla explícita. Adjuntar evidencias, contacto efectivo con un especialista, CSAT y voz conservan sus límites anteriores.
- La biblioteca y las reglas del editor siguen destinadas a un operador local. Esto no convierte el LAB en un panel administrativo multiusuario de producción. Los archivos de resultados siguen protegidos por el acceso al equipo y excluidos de Git.
