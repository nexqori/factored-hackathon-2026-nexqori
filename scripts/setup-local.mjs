import { randomBytes } from 'node:crypto';
import { existsSync, writeFileSync } from 'node:fs';
const path = new URL('../.env', import.meta.url);
if (existsSync(path)) {
  console.log('.env already exists; preserved without changes.');
} else {
  const secret = () => randomBytes(24).toString('base64url');
  const content = [
    '# Local Nexqori credentials. Do not commit or share this file.',
    'CUSTOMER_PASSWORD=' + secret(), 'ADMIN_PASSWORD=' + secret(), 'SECOND_CUSTOMER_PASSWORD=' + secret(),
    'POSTGRES_ADMIN_PASSWORD=' + secret(), 'APP_DATABASE_PASSWORD=' + secret(),
    'APP_ORIGINS=http://localhost:5180,http://127.0.0.1:5180', 'COOKIE_SECURE=false',
    '# Reserved configuration; model adapter not implemented.',
    'INTENT_MODE=off', 'INTENT_PROVIDER=rules', 'INTENT_FALLBACK=rules',
    'INTENT_EXTERNAL_DATA_ALLOWED=false', 'INTENT_TIMEOUT_MS=3000',
    'INTENT_MAX_RETRIES=1', 'INTENT_LOG_RAW_TEXT=false',
    'TYPESAFE_API_KEY=', 'TYPESAFE_MODEL=', ''
  ].join('\n');
  writeFileSync(path, content, { mode: 0o600, flag: 'wx' });
  console.log('Created .env with unique local passwords. Open it to sign in; secrets were not printed.');
}
