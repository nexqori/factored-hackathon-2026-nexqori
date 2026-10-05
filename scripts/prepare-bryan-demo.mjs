// Reproducible synthetic case; generated credentials stay in .local.
import { randomBytes } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
if (process.argv.slice(2).join(' ') !== '--confirm-local') {
  console.error('Uso: node scripts/prepare-bryan-demo.mjs --confirm-local');
  process.exit(1);
}
const folder = resolve(root, '.local/ux-users/bryan-demo');
mkdirSync(folder, { recursive: true });
const manifestPath = resolve(folder, 'manifest.private.json');
if (!existsSync(manifestPath)) {
  writeFileSync(manifestPath, JSON.stringify({ schemaVersion: 1, runId: randomBytes(6).toString('hex'),
    createdAt: new Date().toISOString(), password: randomBytes(24).toString('base64url') }, null, 2),
  { mode: 0o600, flag: 'wx' });
}
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
const child = spawnSync('docker', ['compose', 'exec', '-T', '-e', 'NEXQORI_LOCAL_VERIFY=1',
  'api', 'python', '-m', 'backend.bryan_demo'], {
  cwd: root, input: JSON.stringify(manifest), encoding: 'utf8', windowsHide: true, timeout: 120000,
});
if (child.status !== 0) {
  console.error('No se preparó el perfil. Comprueba la versión de la API. El manifiesto se conserva para reintentar sin duplicarlo.');
  process.exit(1);
}
const result = JSON.parse(child.stdout);
if (result.runId !== manifest.runId || result.users.length !== 1 || result.currency !== 'MXN') {
  throw new Error('Respuesta inconsistente con el perfil solicitado.');
}
writeFileSync(resolve(folder, 'records.private.json'), JSON.stringify(result, null, 2), { mode: 0o600 });
const user = result.users[0];
const guidePath = resolve(folder, 'INICIAR.private.md');
writeFileSync(guidePath, [
  '# Bryan · casos para la demo', '', 'Banco local: http://localhost:5180', '',
  `Correo: ${user.email}`, `Documento: ${user.identityNumber}`, `Contraseña: ${manifest.password}`, '',
  'Moneda: pesos mexicanos (MXN). Datos sintéticos independientes; Camila conserva su historial.',
  result.created ? 'El perfil comienza sin reclamos ni conversaciones.' : 'El perfil ya existía: se conservó su actividad.', '',
  `Saldo de cuenta al preparar: ${(user.balanceMinor / 100).toFixed(2)} MXN.`,
  `Línea del escenario: ${result.scenario.reference}.`, '',
  '## 1. Cobro de teléfono fuera del plan', '',
  'Mensaje: Me cobraron 459 pesos por el teléfono y normalmente pago 299. ¿Puedes revisar qué pasó?', '',
  'Cinco pagos anteriores de 299 MXN. El actual es 459 MXN y está pendiente de procesamiento.',
  'Condiciones del plan: 299 MXN por mes, impuestos incluidos; los adicionales requieren aceptación.',
  'Diferencia: 160 MXN. Una publicación de tarifa no sustituye las condiciones personales.',
  'Nexi debe identificar el movimiento, confirmar contigo y presentar la evidencia para revisión.',
  'Un pago pendiente no equivale a una devolución aprobada ni a una anulación disponible.', '',
  '## 2. Compra fuera de tendencia', '',
  'Mensaje: No reconozco una compra de 2700 pesos en Mercado del Barrio. Quiero revisarla.', '',
  'Cinco compras anteriores: 600, 610, 590, 620 y 580 MXN. Promedio: 600 MXN.',
  'La compra de 2700 MXN está completada. Confirma el registro antes de presentar el reclamo.',
  'El administrador puede revisar una solicitud de devolución; el bot no la aprueba.', '',
  '## Recorrido', '',
  '1. Inicia sesión con este perfil. Abre Movimientos y filtra por comercio.',
  '2. Revisa el detalle o inicia una conversación con Nexi usando uno de los mensajes.',
  '3. Confirma el movimiento y revisa el resumen antes de registrar el reclamo.',
  '4. Consulta Mis reclamos; la revisión administrativa y el resultado se muestran en el expediente.', '',
  'El correo inicial es ficticio; si se personaliza, esta guía conserva el correo actual del perfil. Para recibir notificaciones, verifica el destinatario en Configuración y configura Gmail en el servidor.',
  'No publiques este archivo ni el manifiesto en Git. Repetir la preparación no reinicia el perfil.', '',
].join('\n'), { mode: 0o600 });
console.log(JSON.stringify({ created: result.created, users: 1, currency: result.currency,
  otherRecordsPreserved: result.otherRecordsPreserved, guide: guidePath }, null, 2));
