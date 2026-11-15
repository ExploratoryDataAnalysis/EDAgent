import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch(process.env.CHROMIUM_EXECUTABLE ? { executablePath: process.env.CHROMIUM_EXECUTABLE } : {});
const staging = process.env.STAGING_URL || 'http://127.0.0.1:5178';
const evidence = process.env.SMOKE_OUTPUT;
if (evidence) await mkdir(evidence, { recursive: true });

async function activate(page, control) {
  await control.waitFor();
  for (let i = 0; i < 25; i++) {
    await page.keyboard.press('Tab');
    if (await control.evaluate(e => e === document.activeElement)) {
      assert.notEqual(await control.evaluate(e => getComputedStyle(e).outlineStyle), 'none');
      await page.keyboard.press('Enter');
      return;
    }
  }
  assert.fail('Could not reach the control using Tab');
}

async function downloadResult(page, keyboard = false) {
  const control = page.getByRole('button', { name: 'Download analysis JSON' });
  const [download] = await Promise.all([page.waitForEvent('download'), keyboard ? activate(page, control) : control.click()]);
  return JSON.parse(await readFile(await download.path(), 'utf8'));
}

try {
  for (const width of [390, 1440]) {
    const page = await browser.newPage({ viewport: { width, height: 860 } });
    await page.goto(staging);
    await activate(page, page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Dataset analyser', exact: true }));
    await page.getByRole('heading', { name: 'Dataset analyser' }).waitFor();
    assert.equal(await page.getByRole('link', { name: 'Open approved county aggregates' }).count(), 0);
    await activate(page, page.getByRole('link', { name: 'Open the invented teaching dataset' }));
    await page.getByRole('heading', { name: 'Invented teaching dataset' }).waitFor();
    await activate(page, page.getByRole('button', { name: 'Run analysis' }));
    await page.getByText('Analysis complete.', { exact: true }).waitFor();
    const saved = await downloadResult(page, true);
    assert.equal(saved.provenance.title, 'Invented teaching dataset');
    assert.equal(saved.tables[0].rows[0].median, 8.5);
    if (evidence) await page.screenshot({ path: `${evidence}/teaching-${width}.png`, fullPage: true });
    await activate(page, page.getByRole('link', { name: 'Back to the investigation' }));
    await page.waitForURL(staging + '/');
    await page.close();
    console.log(`PASS 10A keyboard teaching analysis and export at ${width}px`);
  }
  {
    // Seed an existing account through its normal API, then open a protected deep link.
    const page = await browser.newPage();
    const credentials = { email: `phase10-${randomUUID()}@example.com`, password: randomUUID() };
    const account = await page.request.post(staging + '/api/v1/auth/register', { data: credentials });
    assert.equal(account.status(), 201);
    const headers = { Authorization: `Bearer ${(await account.json()).data.access_token}` };
    const upload = await page.request.post(staging + '/api/v1/datasets/upload', { headers, multipart: {
      file: { name: 'invented-account.csv', mimeType: 'text/csv', buffer: Buffer.from('amount\n4\n8\n12\n16\n') },
    } });
    assert.equal(upload.status(), 200);
    const session = await page.request.post(staging + '/api/v1/sessions', { headers, data: {
      dataset_id: (await upload.json()).data.dataset_id, title: 'Existing invented history',
    } });
    assert.equal(session.status(), 201);
    await page.goto(staging + '/history');
    await page.getByLabel('Email').fill(credentials.email);
    await page.getByLabel('Password').fill(credentials.password);
    await page.keyboard.press('Enter');
    await page.getByText('Existing invented history', { exact: true }).waitFor();
    assert.equal(new URL(page.url()).pathname, '/history');
    await page.reload();
    await page.getByText('Existing invented history', { exact: true }).waitFor();
    await page.close();
    console.log('PASS 10A signed-in deep-link return and existing account history');
  }
  if (process.env.FIXTURE_URL && process.env.FIXTURE_LEDGER) {
    const page = await browser.newPage();
    const fixture = process.env.FIXTURE_URL;
    const ledgerPath = process.env.FIXTURE_LEDGER;
    const ledger = await readFile(ledgerPath, 'utf8');
    try {
      await page.goto(fixture + '/analyser');
      await page.getByRole('link', { name: 'Open approved county aggregates' }).click();
      await page.getByRole('button', { name: 'Run analysis' }).click();
      await page.getByText('Analysis complete.', { exact: true }).waitFor();
      const saved = await downloadResult(page);
      assert.equal(saved.provenance.bundle.manifest_sha256, JSON.parse(ledger).descriptive_release.manifest_sha256);
      assert.equal(saved.provenance.approval_date, '2026-11-13');
      assert.equal(saved.provenance.scope.geoid, '42003');
      if (evidence) await page.screenshot({ path: `${evidence}/synthetic-county.png`, fullPage: true });
      await writeFile(ledgerPath, '{}');
      const failure = page.waitForResponse(r => r.url().includes('/county/download') && r.status() === 503);
      await page.getByRole('button', { name: 'Download analysis JSON' }).click();
      await failure;
      await page.getByRole('alert').waitFor();
      assert.equal(await page.getByRole('region', { name: 'Sample analysis result' }).count(), 0);
      await page.reload();
      await page.getByText('The reviewed county aggregates are currently unavailable.').waitFor();
      await page.goto(fixture + '/analyser/sample/teaching');
      await page.getByRole('button', { name: 'Run analysis' }).click();
      await page.getByText('Analysis complete.', { exact: true }).waitFor();
      console.log('PASS 10A synthetic county provenance, withdrawal and independent teaching fallback');
    } finally {
      await writeFile(ledgerPath, ledger);
      await page.close();
    }
  }
} finally {
  await browser.close();
}
