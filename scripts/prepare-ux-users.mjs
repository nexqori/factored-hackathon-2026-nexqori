// Explicit local fixture preparation. Secrets are saved before the DB call so
// retrying a lost response cannot create new identities or lose their passwords.
import { randomBytes } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
if (!args.includes('--confirm-local') || args.some(a => a !== '--confirm-local' && !a.startsWith('--pack='))) {
  console.error('Uso: node scripts/prepare-ux-users.mjs --confirm-local [--pack=equipo-ux]');
  process.exit(1);
}
const packId = args.find(a => a.startsWith('--pack='))?.slice(7) || 'equipo-ux';
if (!/^[a-z0-9][a-z0-9-]{0,39}$/.test(packId)) throw new Error('Nombre de paquete inválido.');
const folder = resolve(root, '.local', 'ux-users', packId);
mkdirSync(folder, { recursive: true });
const manifestPath = resolve(folder, 'manifest.private.json');
if (!existsSync(manifestPath)) {
  const definitions = JSON.parse(readFileSync(resolve(root, 'backend/ux_scenarios.json'), 'utf8')).cases;
  const manifest = { schemaVersion: 1, packId, runId: randomBytes(6).toString('hex'), createdAt: new Date().toISOString(),
    passwords: Object.fromEntries(definitions.map(c => [c.id, randomBytes(24).toString('base64url')])) };
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), { mode: 0o600, flag: 'wx' });
}
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
if (manifest.packId !== packId) throw new Error('El manifiesto no corresponde a este paquete.');
const child = spawnSync('docker', ['compose', 'exec', '-T', '-e', 'NEXQORI_LOCAL_VERIFY=1',
  'api', 'python', '-m', 'backend.ux_fixtures'], {
  cwd: root, input: JSON.stringify(manifest), encoding: 'utf8', windowsHide: true, timeout: 120000, maxBuffer: 1024 * 1024,
});
if (child.status !== 0) {
  console.error('No se preparó el paquete. Comprueba Docker y que la API tenga esta versión del código. El manifiesto privado se conserva para reintentar.');
  process.exit(1);
}
const result = JSON.parse(child.stdout);
if (result.runId !== manifest.runId || result.packId !== packId || result.users.length !== 5) {
  throw new Error('La respuesta no corresponde al paquete solicitado.');
}
writeFileSync(resolve(folder, 'records.private.json'), JSON.stringify(result, null, 2), { mode: 0o600 });
const guide = ['# Accesos privados · cinco pruebas UX', '', 'Sólo para el banco local: http://localhost:5180',
  '', `Paquete: ${packId}. ${result.created ? 'Creado sin reclamos ni conversaciones previas.' : 'Ya existía: se conservaron sus operaciones y conversaciones.'}`,
  '', 'No compartas este archivo por Git. Las personas y operaciones son ficticias. La ejecución de consultas del chat usa los proveedores que estén configurados.', ''];
for (const user of result.users) {
  guide.push(`## ${user.case.name} · ${user.case.title}`, '', `Correo: ${user.email}`, `Documento: ${user.identityNumber}`,
    `Contraseña: ${manifest.passwords[user.case.id]}`, '', `Movimiento principal: ${user.transactionId}`,
    `Movimiento alternativo: ${user.alternateTransactionId}`, `Cuenta para transferencias: ${user.accountReference} · terminación ${user.accountLast4}`,
    `Saldo actual de la cuenta al preparar esta guía: ${(user.balanceMinor / 100).toFixed(2)} MXN`,
    `Periodo anterior: ${user.previousMonth.startDate} a ${user.previousMonth.endDate}`, '',
    `Mensaje sugerido: ${user.case.messages.es}`, '', `Resultado esperado: ${user.case.expected}`, '',
    'Referencias de servicios:', '', ...user.bills.map(b => `- ${b.serviceId}: ${b.reference} · ${(b.amountMinor / 100).toFixed(2)} MXN`), '');
}
guide.push('Repetir el mismo comando recupera este paquete; no restablece saldos ni reclamos. Para otro grupo limpio, usa un nombre --pack diferente.', '');
const guidePath = resolve(folder, 'INICIAR.private.md');
writeFileSync(guidePath, guide.join('\n'), { mode: 0o600 });
console.log(JSON.stringify({ packId, created: result.created, users: result.users.length, otherRecordsPreserved: result.otherRecordsPreserved, guide: guidePath }, null, 2));
