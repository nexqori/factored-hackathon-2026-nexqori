import { test } from 'vitest';
import assert from 'node:assert/strict';
import { validateVerificationRecords } from './verification-user.mjs';

function fixture() {
  const packId = 'verificacion-ui-0123456789ab', runId = 'abcdef012345';
  return { packId, manifest: { schemaVersion: 1, packId, runId,
    passwords: { cargo: 'Only-for-isolated-manifest-validation' } },
  records: { schemaVersion: 1, packId, runId, users: [{ case: { id: 'cargo', merchant: 'Empresa Telefónica' },
    userId: 'ux-user-' + runId + '-cargo', email: 'ux-' + runId + '-cargo@nexqori.com',
    identityNumber: 'UX' + runId.toUpperCase() + '1' }, {}, {}, {}, {}] } };
}

test('returns only the selected dedicated test customer', () => {
  const input = fixture(), user = validateVerificationRecords(input.manifest, input.records, input.packId);
  assert.equal(user.email, input.records.users[0].email);
  assert.equal(user.identityNumber, input.records.users[0].identityNumber);
  assert.equal(user.password, input.manifest.passwords.cargo);
  assert.equal(user.merchant, 'Empresa Telefónica');
});

for (const change of ['human-ux-pack', 'existing-owner', 'existing-email', 'mismatched-run', 'missing-password']) {
  test('rejects unsafe test credentials: ' + change, () => {
    const input = fixture();
    if (change === 'human-ux-pack') input.packId = input.manifest.packId = input.records.packId = 'equipo-ux';
    if (change === 'existing-owner') input.records.users[0].userId = 'andrea';
    if (change === 'existing-email') input.records.users[0].email = 'andrea@nexqori.com';
    if (change === 'mismatched-run') input.records.runId = '111111111111';
    if (change === 'missing-password') delete input.manifest.passwords.cargo;
    assert.throws(() => validateVerificationRecords(input.manifest, input.records, input.packId));
  });
}
