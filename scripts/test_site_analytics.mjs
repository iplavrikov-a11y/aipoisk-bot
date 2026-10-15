import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const output = mkdtempSync(join(tmpdir(), 'tenderlex-analytics-test-'));
try {
  execFileSync(process.execPath, [join(root, 'site/node_modules/typescript/bin/tsc'),
    join(root, 'site/src/lib/analytics.ts'), '--module', 'commonjs', '--target', 'es2020',
    '--lib', 'es2020,dom', '--strict', '--skipLibCheck', '--outDir', output], { stdio: 'inherit' });
  const require = createRequire(import.meta.url);
  const analytics = require(join(output, 'analytics.js'));
  const calls = [];
  globalThis.window = { ym: (...args) => calls.push(args), location: { origin: 'https://tenderlex.ru' } };
  analytics.trackGoal('registration_success');
  assert.equal(calls.length, 0, 'unknown consent never sends a goal');
  analytics.configureAnalytics('109753178', true);
  analytics.trackGoal('task_started', { module: 'exact_product', email: 'private@example.org', text: 'PRIVATE TZ', token: 'SECRET' });
  assert.deepEqual(calls.at(-1), [109753178, 'reachGoal', 'task_started', { module: 'exact_product' }]);
  analytics.trackGoal('invented_goal', { module: 'supplier_search' });
  assert.equal(calls.length, 1, 'unknown goals are rejected');
  assert.equal(analytics.safeAnalyticsUrl('https://tenderlex.ru/cabinet?email_verify_token=SECRET#email=private@example.org'), 'https://tenderlex.ru/cabinet');
  assert.equal(analytics.safeAnalyticsUrl('https://external.example/search?q=private'), 'https://external.example/search');
  assert.equal(analytics.safeAnalyticsUrl('javascript:alert(1)'), '');
  assert.equal(analytics.safeAnalyticsUrl('/api/customer/jobs/123/download'), '', 'private API URLs are rejected');
  analytics.trackGoal('result_downloaded', { module: 'SECRET', kind: 'file', href: 'private' });
  assert.deepEqual(calls.at(-1), [109753178, 'reachGoal', 'result_downloaded', {}]);
  analytics.configureAnalytics('109753178', false);
  analytics.trackGoal('registration_success');
  assert.equal(calls.length, 2, 'denied consent never sends a goal');
  analytics.configureAnalytics('invalid', true);
  analytics.trackGoal('registration_success');
  assert.equal(calls.length, 2, 'invalid counter never sends a goal');
  analytics.configureAnalytics('109753178', true);
  window.ym = () => { throw new Error('SDK blocked'); };
  assert.doesNotThrow(() => analytics.trackGoal('registration_success'), 'analytics cannot break a successful business action');
  console.log('PASS: consent, goal allowlist, private URL and payload protection, SDK failure isolation');
} finally {
  rmSync(output, { recursive: true, force: true });
  delete globalThis.window;
}
