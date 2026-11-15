import assert from 'node:assert/strict';
import { mkdir, readFile } from 'node:fs/promises';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch(process.env.CHROMIUM_EXECUTABLE ? { executablePath: process.env.CHROMIUM_EXECUTABLE } : {});
const staging = process.env.STAGING_URL || 'http://127.0.0.1:5178';
const evidence = process.env.SMOKE_OUTPUT;
if (evidence) await mkdir(evidence, { recursive: true });

async function keyboard(page, target) {
  await target.waitFor();
  for (let i = 0; i < 45; i++) {
    if (await target.evaluate(e => e === document.activeElement)) {
      assert.notEqual(await target.evaluate(e => getComputedStyle(e).outlineStyle), 'none');
      await page.keyboard.press('Enter');
      return;
    }
    await page.keyboard.press('Tab');
  }
  assert.fail('Guest control was unreachable by keyboard');
}

async function startGuest(page) {
  await page.goto(staging + '/analyser');
  await keyboard(page, page.getByRole('button', { name: 'Start a private guest session' }));
  await page.waitForURL('**/upload');
  await page.getByRole('region', { name: 'Private guest session' }).waitFor();
  assert.equal(await page.getByRole('link', { name: 'AI Dataset Chat' }).count(), 0);
}

try {
  for (const width of [390, 1440]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await startGuest(page);
    const choose = page.getByRole('button', { name: 'Browse for a dataset' });
    const [badFile] = await Promise.all([page.waitForEvent('filechooser'), keyboard(page, choose)]);
    await badFile.setFiles({ name: 'unsupported.txt', mimeType: 'text/plain', buffer: Buffer.from('invalid') });
    await page.getByRole('alert').waitFor();
    const [file] = await Promise.all([page.waitForEvent('filechooser'), keyboard(page, choose)]);
    await file.setFiles({
      name: 'invented-guest.csv', mimeType: 'text/csv',
      buffer: Buffer.from('category,amount\nA,10\nA,14\nB,18\nB,22\n'),
    });
    await keyboard(page, page.getByRole('button', { name: 'Launch Analysis Workspace' }));
    const run = page.getByRole('button', { name: 'Run', exact: true }).first();
    await keyboard(page, run);
    const csv = page.getByRole('button', { name: 'CSV', exact: true }).first();
    const [download] = await Promise.all([page.waitForEvent('download'), keyboard(page, csv)]);
    assert.ok((await readFile(await download.path(), 'utf8')).length > 20);
    if (evidence) await page.screenshot({ path: `${evidence}/guest-analysis-${width}.png`, fullPage: true });
    await page.reload();
    await page.getByRole('region', { name: 'Private guest session' }).waitFor();
    await run.waitFor();
    await keyboard(page, page.getByRole('button', { name: 'Clear guest session', exact: true }));
    await keyboard(page, page.getByRole('button', { name: 'Clear session', exact: true }));
    await page.getByText('Private guest session cleared.').waitFor();
    await page.goto(staging + '/analyser');
    await page.getByRole('button', { name: 'Start a private guest session' }).waitFor();
    await page.close();
    console.log(`PASS 10B keyboard guest upload, error recovery, analysis, export, reload and clear at ${width}px`);
  }

  const page = await browser.newPage();
  // Advance the browser clock to the actual deadline advertised by the server.
  await page.clock.install();
  await startGuest(page);
  const expires = await page.locator('time').getAttribute('datetime');
  await page.clock.fastForward(Date.parse(expires) - await page.evaluate(() => Date.now()) + 1000);
  await page.getByText(/Your private guest session ended/).waitFor();
  await page.getByRole('button', { name: 'Start a private guest session' }).waitFor();
  await page.close();
  console.log('PASS 10B guest expiry notice and fresh entry');
} finally {
  await browser.close();
}
