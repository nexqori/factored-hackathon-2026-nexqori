// UI checks get their own persistent local customer. Human UX profiles are never
// accepted here, even when a caller supplies an existing private records file.
import { randomBytes } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { readFileSync, realpathSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const packPattern = /^verificacion-ui-[a-f0-9]{12}$/;

export function validateVerificationRecords(manifest, records, packId) {
  if (!packPattern.test(packId) || manifest.packId !== packId || records.packId !== packId
      || manifest.schemaVersion !== 1 || records.schemaVersion !== 1
      || !/^[a-f0-9]{12}$/.test(manifest.runId) || records.runId !== manifest.runId
      || !Array.isArray(records.users) || records.users.length !== 5) {
    throw new Error('Se requiere un paquete separado de verificación de interfaz.');
  }
  const person = records.users.find(user => user.case?.id === 'cargo');
  const suffix = manifest.runId + '-cargo';
  const password = manifest.passwords?.cargo;
  if (!person || person.userId !== 'ux-user-' + suffix || person.email !== 'ux-' + suffix + '@nexqori.com'
      || person.identityNumber !== 'UX' + manifest.runId.toUpperCase() + '1'
      || person.case.merchant !== 'Empresa Telefónica'
      || typeof password !== 'string' || password.length < 24 || password.length > 128) {
    throw new Error('Los datos privados no corresponden al titular de verificación.');
  }
  return { email: person.email, password, identityNumber: person.identityNumber,
    merchant: person.case.merchant, packId };
}

export function verificationUser() {
  const origin = new URL(process.env.NEXQORI_URL || 'http://localhost:5180');
  if (!['http:', 'https:'].includes(origin.protocol) || !['localhost', '127.0.0.1', '[::1]'].includes(origin.hostname)
      || origin.username || origin.password || origin.pathname !== '/' || origin.search || origin.hash) {
    throw new Error('Los usuarios de verificación sólo se usan con el banco local.');
  }
  let recordsFile = process.env.NEXQORI_TEST_USER_FILE;
  if (!recordsFile) {
    const packId = 'verificacion-ui-' + randomBytes(6).toString('hex');
    const prepared = spawnSync(process.execPath, [join(root, 'scripts/prepare-ux-users.mjs'),
      '--confirm-local', '--pack=' + packId], { cwd: root, encoding: 'utf8', windowsHide: true,
      timeout: 150000, maxBuffer: 1024 * 1024 });
    if (prepared.status !== 0) throw new Error('No se pudo preparar el usuario de verificación local. Comprueba Docker.');
    recordsFile = join(root, '.local/ux-users', packId, 'records.private.json');
  }
  const path = resolve(recordsFile), folder = dirname(path), packId = basename(folder);
  const uxRoot = realpathSync(join(root, '.local/ux-users'));
  if (basename(path) !== 'records.private.json' || !packPattern.test(packId)
      || dirname(realpathSync(folder)) !== uxRoot || realpathSync(path) !== join(realpathSync(folder), 'records.private.json')) {
    throw new Error('NEXQORI_TEST_USER_FILE debe señalar un paquete privado verificacion-ui; equipo-ux está reservado.');
  }
  const manifestFile = join(folder, 'manifest.private.json');
  if (realpathSync(manifestFile) !== join(realpathSync(folder), 'manifest.private.json')) {
    throw new Error('El manifiesto debe pertenecer al mismo paquete privado.');
  }
  const user = validateVerificationRecords(JSON.parse(readFileSync(manifestFile, 'utf8')),
    JSON.parse(readFileSync(path, 'utf8')), packId);
  console.log(JSON.stringify({ verificationUserFile: path, testPack: packId }));
  return { ...user, recordsFile: path };
}
