// Persistent, isolated verification profile. Never edits a manual user's cards.
import { chromium, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { spawnSync } from 'node:child_process';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { strict as assert } from 'node:assert';
import { verificationUser } from './verification-user.mjs';
const person = verificationUser(), origin = 'http://localhost:5180';
const records = JSON.parse(readFileSync(person.recordsFile, 'utf8'));
const profile = records.users.find(p => p.case.id === 'cargo');
const folder = '.local/verification/card-kinds-' + person.packId;
mkdirSync(folder, { recursive: true });
const prepare = spawnSync('docker', ['compose', 'exec', '-T', 'api', 'python', '-c', `
import json,sys
from sqlalchemy import select
from backend.db import make_engine,make_sessions
from backend.models import Product,CardProfile,Transaction,AuditEvent
p=json.load(sys.stdin)
uid=p['userId']
assert uid.startswith('ux-user-') and p['packId'].startswith('verificacion-ui-')
with make_sessions(make_engine())() as db:
 with db.begin():
    card=db.get(Product,p['cardId']); assert card.user_id==uid
    card.card_kind='credit'
    ident=card.id+'-debit'
    if not db.get(Product,ident):
        db.add(Product(id=ident,user_id=uid,type='card',card_kind='debit',last4='4192',currency='MXN'))
        db.flush()
        db.add(CardProfile(product_id=ident,user_id=uid,provider_ref=ident,expiry_month=12,expiry_year=2030,settlement_product_id=p['accountId']))
        tx=db.scalar(select(Transaction).where(Transaction.user_id==uid,Transaction.product_id==p['accountId'],Transaction.amount_minor<0))
        assert tx is not None
        tx.product_id=ident
        db.add(AuditEvent(id=ident+'-created',user_id=uid,actor_id=uid,action='card_kind_fixture_created'))
print(json.dumps({'credit':card.id,'debit':ident}))
`], { input: JSON.stringify({ ...profile, packId: person.packId }), encoding: 'utf8', windowsHide: true, timeout: 120000 });
assert.equal(prepare.status, 0, 'Card kind fixture failed (private output suppressed)');
const ids = JSON.parse(prepare.stdout);
const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge', headless: true });
const context = await browser.newContext({ viewport: { width: 1512, height: 1050 } });
const page = await context.newPage();
const report = { checks: [], accessibility: [], errors: [] };
page.on('pageerror', e => report.errors.push(e.message));
await page.route('**/api/assistant/capabilities', route => route.fulfill({ json: { connected: false, providers: {} } }));
try {
  const login = await context.request.post(origin + '/api/auth/login', { headers: { Origin: origin }, data: { identifier: person.email, password: person.password } });
  assert.equal(login.status(), 200);
  const cards = (await (await context.request.get(origin + '/api/cards')).json()).cards;
  assert.equal(cards.find(c => c.id === ids.credit).cardKind, 'credit');
  assert.equal(cards.find(c => c.id === ids.debit).cardKind, 'debit');
  await page.goto(origin + '/cards');
  for (const lang of ['es', 'en', 'pt']) {
    const copy = JSON.parse(readFileSync('src/locales/' + lang + '.json', 'utf8'));
    await page.locator('.language-trigger').click();
    await page.locator('[data-locale="' + lang + '"]').click();
    for (const width of [1512, 390]) {
      await page.setViewportSize({ width, height: 1050 });
      for (const kind of ['credit', 'debit']) {
        await expect(page.locator('[data-card-id="' + ids[kind] + '"] .bank-card')).toContainText(copy[kind + 'Card']);
      }
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      const scan = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
      assert.equal(scan.violations.length, 0, JSON.stringify(scan.violations.map(v => v.id)));
      report.accessibility.push(lang + '-' + width);
      await page.screenshot({ path: folder + '/' + lang + '-' + width + '.png', fullPage: true });
    }
    await page.setViewportSize({ width: 1512, height: 1050 });
    for (const kind of ['credit', 'debit']) {
      await page.goto(origin + '/movements?product=' + encodeURIComponent(ids[kind]));
      await expect(page.locator('.movement-filters select').first()).toHaveValue(ids[kind]);
      await expect(page.locator('.movement-filters select').first().locator('option:checked')).toContainText(copy[kind + 'Card']);
      await expect(page.locator('.movement-meta').first()).toContainText(copy[kind + 'Card']);
    }
    report.checks.push({ lang, bothCardsVisible: true, movementLabels: true });
    await page.goto(origin + '/cards');
  }
  assert.deepEqual(report.errors, []);
  writeFileSync(folder + '/report.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ folder, ...report }));
} finally { await browser.close(); }
