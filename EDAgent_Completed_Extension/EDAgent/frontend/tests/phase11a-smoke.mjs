import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import { createServer } from 'node:http';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const site = process.env.STAGING_URL || 'http://127.0.0.1:5490';
const port = Number(process.env.CHAT_STUB_PORT || 0);
const evidence = process.env.SMOKE_OUTPUT;
if (evidence) await mkdir(evidence, { recursive: true });

let held;
let calls = 0;
// The actual signed-in API uses its OpenAI-compatible adapter. This stub only listens
// on loopback and accepts the fixture model and synthetic credential.
const stub = createServer(async (req, res) => {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const payload = JSON.parse(Buffer.concat(chunks));
  assert.equal(req.url, '/v1/chat/completions');
  assert.equal(req.headers.authorization, 'Bearer invented-key');
  assert.equal(payload.model, 'loopback-stub');
  calls++;
  const user = payload.messages.at(-1).content;
  const planner = payload.messages[0].content.includes('planning component');
  const question = user.split('User question: ').at(-1).split('\n')[0];
  if (planner && question === 'Check credential failure') {
    res.writeHead(401).end('synthetic provider rejection');
    return;
  }
  if (planner && question.startsWith('Late ')) {
    held.arrived();
    await held.release;
  }
  const result = planner
    ? { type: 'plan', plan: { operation: 'descriptive_stats', target_columns: ['wait_minutes'] } }
    : JSON.parse(user.split('<result_facts>')[1].split('</result_facts>')[0]);
  const answer = planner ? result : { result_id: result.result_id, focus: 'scope' };
  if (!planner && question === 'Find the median in minutes') answer.claim = 'The maximum is 8 hours.';
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ choices: [{ message: { content: JSON.stringify(answer) } }] }));
});

async function keyboard(page, locator, activate = true) {
  await locator.waitFor();
  for (let i = 0; i < 55; i++) {
    if (await locator.evaluate(e => e === document.activeElement)) {
      if (activate) await page.keyboard.press('Enter');
      return;
    }
    await page.keyboard.press('Tab');
  }
  assert.fail('Control was unreachable by keyboard');
}

async function seed(page) {
  const auth = await page.request.post(site + '/api/v1/auth/register', {
    data: { email: `phase11-${randomUUID()}@example.com`, password: 'invented-password-11', full_name: 'Test Reader' },
  });
  assert.equal(auth.status(), 201, await auth.text());
  const { access_token: token, user } = (await auth.json()).data;
  const headers = { Authorization: `Bearer ${token}` };
  async function upload(name, values) {
    const response = await page.request.post(site + '/api/v1/datasets/upload', {
      headers, multipart: { file: { name, mimeType: 'text/csv', buffer: Buffer.from('wait_minutes\n' + values + '\n') } },
    });
    assert.equal(response.status(), 200, await response.text());
    return (await response.json()).data.dataset_id;
  }
  const first = await upload('waiting-room.csv', '2\n6\n10\n14');
  await upload('other-room.csv', '12\n16\n20\n24');
  await page.goto(site + '/analyser');
  await page.evaluate(({ token, first }) => {
    localStorage.setItem('edagent_token', token);
    localStorage.setItem('edagent_active_dataset_id', first);
  }, { token, first });
  await page.goto(site + '/chat');
  return { first, headers, user };
}

async function suppressLateReply(page, question, switchView) {
  let release, arrived, complete;
  const ready = new Promise((resolve, reject) => {
    arrived = resolve;
    AbortSignal.timeout(12000).addEventListener('abort', () => reject(new Error('Stub did not receive the held request')));
  });
  const finished = new Promise(resolve => { complete = resolve; });
  held = { arrived, release: new Promise(resolve => { release = resolve; }) };
  const path = '**/api/v1/chat/message';
  // Fetch outside the page request so the real backend can finish after the browser
  // aborts delivery. This exercises a late success, not only a canceled transport.
  const forward = async route => {
    try {
      const response = await route.fetch({ timeout: 15000 });
      await route.fulfill({ response }).catch(() => {});
      complete((await response.json()).data);
    } catch {
      complete(null);
    }
  };
  await page.route(path, forward);
  try {
    const input = page.getByRole('textbox', { name: 'Question about your dataset' });
    await input.fill(question);
    await input.press('Enter');
    await page.getByRole('status').filter({ hasText: 'Planning and running' }).waitFor();
    await ready;
    await switchView();
    release();
    const old = await finished;
    assert.equal(old?.kind, 'analysis');
    assert.equal(await page.getByText(question, { exact: true }).count(), 0);
    assert.equal(await page.getByText('Verified analysis', { exact: true }).count(), 0);
    return old;
  } finally {
    release();
    await page.unroute(path, forward);
  }
}

if (port) {
  await new Promise((resolve, reject) => {
    stub.once('error', reject);
    stub.listen(port, '127.0.0.1', resolve);
  });
}
const browser = await chromium.launch(process.env.CHROMIUM_EXECUTABLE ? { executablePath: process.env.CHROMIUM_EXECUTABLE } : {});
try {
  for (const width of [390, 1440]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    page.setDefaultTimeout(15000);
    const { first, headers, user } = await seed(page);
    const main = page.getByRole('main');
    const manual = main.getByRole('link', { name: port ? 'Run manually in Analysis Workspace' : 'Analysis Workspace', exact: true });
    const input = page.getByRole('textbox', { name: 'Question about your dataset' });
    if (port) {
      await keyboard(page, main.getByRole('button', { name: 'Start chat' }));
      await keyboard(page, input, false);
      await page.keyboard.type('Find the median in minutes');
      await page.keyboard.press('Enter');
      await main.getByText('Computed summary (AI explanation unavailable)', { exact: true }).waitFor();
      await main.getByText(/'wait_minutes'.*median 8/).first().waitFor();
      assert.doesNotMatch(await main.innerText(), /8 hours/);

      const before = calls;
      await input.fill('Check credential failure');
      await input.press('Enter');
      await main.getByText('AI unavailable', { exact: true }).waitFor();
      await page.getByRole('status').filter({ hasText: 'rejected the server' }).waitFor({ state: 'attached' });
      assert.equal(calls - before, 1);
      const me = await page.request.get(site + '/api/v1/auth/me', { headers });
      assert.equal((await me.json()).data.id, user.id);
      assert.ok(await page.evaluate(() => localStorage.getItem('edagent_token')));
      if (evidence) await page.screenshot({ path: `${evidence}/chat-provider-recovery-${width}.png` });
    } else {
      await main.getByRole('status').filter({ hasText: 'AI chat is disabled' }).waitFor();
      assert.equal(await input.isDisabled(), true);
    }
    await keyboard(page, manual);
    await page.waitForURL('**/workspace');
    const summary = main.getByRole('listitem').filter({ hasText: /Summary statistics/i }).first();
    const [response] = await Promise.all([
      page.waitForResponse('**/api/v1/analysis/execute'),
      keyboard(page, summary.getByRole('button', { name: 'Run', exact: true })),
    ]);
    const result = (await response.json()).data;
    assert.equal(result.dataset_id, first);
    assert.equal(result.tables[0].rows[0].median, 8);
    await main.getByText(/'wait_minutes'.*median 8/).first().waitFor();
    if (evidence) await page.screenshot({ path: `${evidence}/chat-manual-median-${width}.png` });
    if (port) {
      await page.goto(site + '/chat');
      const firstLate = await suppressLateReply(page, 'Late session answer', async () => {
        await main.getByRole('button', { name: 'New chat' }).click();
        await main.getByText('Late session answer', { exact: true }).waitFor({ state: 'detached' });
        await page.waitForFunction(() => document.querySelector('textarea[aria-label="Question about your dataset"]:enabled'));
      });
      const secondLate = await suppressLateReply(page, 'Late dataset answer', async () => {
        await page.getByRole('button', { name: 'waiting-room.csv', exact: true }).click();
        await page.getByRole('button', { name: /other-room.csv/ }).click();
        await main.getByText('other-room.csv', { exact: true }).waitFor();
      });
      assert.notEqual(firstLate.session_id, secondLate.session_id);
      assert.equal(firstLate.analysis_result.dataset_id, first);
      assert.equal(secondLate.analysis_result.dataset_id, first);
    }
    await page.close();
    console.log(`PASS 11A ${port ? 'stub fallback, credential rejection, keyboard manual recovery, and both stale scopes' : 'disabled chat and keyboard manual recovery'} at ${width}px`);
  }
} finally {
  await browser.close();
  if (port) stub.closeAllConnections();
  stub.close();
}
