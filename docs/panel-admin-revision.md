# Bandeja de reclamos

El panel administrativo organiza los casos en páginas de hasta cinco registros. En pantallas de escritorio bajas, reduce la cantidad por página para mostrar las tarjetas completas. Buscar por referencia, cliente o movimiento y filtrar por etapa reinicia la página y retira la selección anterior. Abrir un expediente conserva el filtro de cliente; no lo cambia automáticamente al titular elegido. La URL guarda filtros, página y caso para recargar o compartir la misma vista dentro de una sesión administrativa.

Las flechas del expediente recorren los resultados filtrados, también entre páginas. En móvil, la bandeja y el expediente se muestran por separado; Volver a la bandeja recupera la página y filtros.

## Revisar un caso

1. Abre un caso en la bandeja.
2. Lee Resumen: relato, estado, contexto disponible e información por contrastar.
3. Consulta Evidencia, Conversaciones o Documentos cuando lo necesites. Los PDF mantienen apertura y descarga autenticadas.
4. Abre Gestionar para confirmar cada etapa. Aprobar un reclamo no genera un abono: el reembolso conserva su confirmación y contraseña independientes.
5. Consulta Actividad para revisar la trazabilidad. Técnico mantiene el JSON para administración.

Cambiar de sección conserva el borrador de revisión del mismo caso. Cambiar de expediente inicia los controles del nuevo titular; una casilla de aprobación no se reutiliza en otro caso. La selección y la paginación no ejecutan operaciones. La interfaz consume el listado administrativo existente y pagina en el navegador; no añade paginación al servidor ni cambia sus permisos.

## Validación

```powershell
npm test
npm run build
node scripts/nexqori-admin-decision.mjs
$env:NEXQORI_ADMIN_MOBILE='1'
node scripts/nexqori-admin-decision.mjs
Remove-Item Env:NEXQORI_ADMIN_MOBILE
npm run test:claims
npm run test:ui
```

El ensayo administrativo usa un servidor aislado en 5192 y prueba aprobación, rechazo y pago pendiente en ES/EN/PT, conservación de borradores, filtros, páginas y accesibilidad. `test:claims` usa perfiles de verificación separados en PostgreSQL y comprueba PDF, conversaciones, trazabilidad y aislamiento. Ninguno de esos ensayos necesita tocar los reclamos manuales de Bryan o Camila.
