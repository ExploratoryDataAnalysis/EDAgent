import assert from 'node:assert/strict';
import { mkdir, readFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';

// Run with the Playwright package used by the local browser environment.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fixture = process.env.FIXTURE_URL || 'http://127.0.0.1:5177';
const staging = process.env.STAGING_URL;
const evidence = process.env.SMOKE_OUTPUT;
if (evidence) await mkdir(evidence, { recursive: true });
const browser = await chromium.launch(process.env.CHROMIUM_EXECUTABLE ? { executablePath: process.env.CHROMIUM_EXECUTABLE } : {});

async function screenshot(page, name) {
  if (evidence) await page.screenshot({ path: `${evidence}/${name}.png`, fullPage: true });
}

async function tabTo(page, locator) {
  for (let step = 0; step < 50; step++) {
    if (await locator.evaluate(element => element === document.activeElement)) return;
    await page.keyboard.press('Tab');
  }
  assert.fail('Control could not be reached with Tab');
}

const widths = { desktop: 1440, narrow: 390 };
try {
  for (const [size, width] of Object.entries(widths)) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.goto(`${fixture}/road-safety`);
    await page.getByText('Synthetic test fixture. Counts are invented for verification.').waitFor();
    assert.match(await page.getByRole('region', { name: 'Crash totals' }).innerText(), /Reported crashes\s+24[\s\S]+Mapped crashes\s+20/);
    await tabTo(page, page.getByText('Annual trends data table', { exact: true }));
    await page.keyboard.press('Enter');
    const annual = page.getByRole('table', { name: 'Annual reported crashes and severity' });
    assert.match(await annual.getByRole('row', { name: /^2015/ }).innerText(), /Unavailable\s+Unavailable/);
    const fields = page.getByRole('table', { name: '2024 hour and illumination coverage' });
    assert.match(await fields.getByRole('row', { name: /^Populated illumination/ }).innerText(), /0\s+12\s+12\s+0\.00%/);
    const image = page.getByRole('img', { name: /^County boundary/ });
    await image.waitFor();
    await page.waitForFunction(() => document.querySelector('figure img')?.naturalWidth > 0);
    assert.equal(await page.locator('.js-plotly-plot').count(), 3);
    assert.ok(await page.locator('main').evaluate(element => element.scrollWidth <= element.clientWidth + 1));
    await screenshot(page, `fixture-overview-${size}`);

    const next = page.getByRole('link', { name: 'Open the illustrative scenario workspace' });
    await tabTo(page, next);
    await page.keyboard.press('Enter');
    await page.getByRole('heading', { name: 'Illustrative scenario', exact: true }).waitFor();
    const select = page.getByLabel('Select a treatment reference');
    await select.getByRole('option', { name: 'Roadway lighting' }).waitFor({ state: 'attached' });
    assert.equal(await select.getByRole('option').count(), 7);
    const factor = page.getByLabel('Hypothetical CMF', { exact: true });
    await factor.fill('1.05');
    await select.selectOption('lighting');
    assert.equal(await factor.inputValue(), '');
    await page.getByText('REFERENCE_ONLY', { exact: true }).waitFor();
    await page.getByText('General candidate and methodology references. No lighting study or rating is documented.').waitFor();
    const years = page.getByLabel('Analysis period (years)');
    await tabTo(page, years);
    await page.keyboard.type('2');
    await page.keyboard.press('Tab');
    await page.keyboard.type('10');
    await page.keyboard.press('Tab');
    await page.keyboard.type('0.800000');
    await page.getByLabel('Lower factor').fill('0.6');
    await page.getByLabel('Upper factor').fill('1.3');
    const calculate = page.getByRole('button', { name: 'Calculate scenario' });
    await tabTo(page, calculate);
    const submission = page.waitForRequest(request => request.method() === 'POST' && request.url().endsWith('/interventions/scenarios'));
    await page.keyboard.press('Enter');
    const body = (await submission).postDataJSON();
    assert.equal(body.schema_version, '1');
    assert.equal(body.hypothetical_baseline_n, '10');
    assert.equal(body.cmf.value, '0.800000');
    const result = page.getByRole('status').filter({ hasText: 'Hypothetical results' });
    await result.waitFor();
    assert.match(await result.innerText(), /8\.00[\s\S]+2\.00 \(fewer hypothetical crashes\)[\s\S]+-3\.00 to 4\.00/);
    assert.ok(await page.locator('main').evaluate(element => element.scrollWidth <= element.clientWidth + 1));
    await screenshot(page, `fixture-calculator-${size}`);
    await factor.fill('0');
    await result.waitFor({ state: 'detached' });
    await calculate.click();
    await page.getByRole('alert').filter({ hasText: 'greater than 0' }).waitFor();
    assert.equal(await result.count(), 0);

    // Hold a successful server response while the user changes the inputs.
    let releaseResponse;
    let responseReady;
    const ready = new Promise(resolve => { responseReady = resolve; });
    const hold = new Promise(resolve => { releaseResponse = resolve; });
    const scenarioUrl = '**/api/v1/interventions/scenarios';
    const delayed = async route => {
      const response = await route.fetch();
      responseReady(response.status());
      await hold;
      await route.fulfill({ response }).catch(() => {});
    };
    await page.route(scenarioUrl, delayed);
    await factor.fill('0.8');
    await calculate.click();
    assert.equal(await ready, 200);
    await factor.fill('0.9');
    releaseResponse();
    await page.unrouteAll({ behavior: 'wait' });
    assert.equal(await result.count(), 0);

    // Exercise the actual refusal by adding forbidden context in transit.
    await page.route(scenarioUrl, route => route.continue({ postData: { ...route.request().postDataJSON(), site_id: 'Station 375' } }));
    await calculate.click();
    await page.getByRole('alert').filter({ hasText: 'REAL_SITE_BENEFIT_UNAVAILABLE' }).waitFor();
    assert.equal(await result.count(), 0);
    await page.close();
    console.log(`PASS ${size} ${width}px — synthetic Overview, keyboard access, nulls and zeros, calculator validation, stale responses, real-site refusal`);
  }

  if (staging) {
    for (const [size, width] of Object.entries(widths)) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      await page.goto(`${staging}/road-safety`);
      await page.getByRole('heading', { name: 'Reviewed data unavailable' }).waitFor();
      const response = await page.request.get(`${staging}/api/v1/road-safety/overview/provenance`);
      assert.equal(response.status(), 503);
      assert.deepEqual((await response.json()).detail, {
        code: 'OVERVIEW_UNAVAILABLE', message: 'The reviewed Road Safety Overview dataset is unavailable.',
        approval_state: null, data: null,
      });
      assert.equal(await page.getByRole('region', { name: 'Crash totals' }).count(), 0);
      await screenshot(page, `staging-pending-${size}`);
      await page.close();
      console.log(`PASS ${size} ${width}px — real D7 staging pending approval (HTTP 503)`);
    }

    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(`${staging}/illustrative-scenario`);
    await page.getByRole('option', { name: 'Roadway lighting' }).waitFor({ state: 'attached' });
    await page.getByLabel('Analysis period (years)').fill('1');
    await page.getByLabel('Hypothetical baseline crash count').fill('10');
    await page.getByLabel('Hypothetical CMF', { exact: true }).fill('1.25');
    await page.getByRole('button', { name: 'Calculate scenario' }).click();
    await page.getByText('-2.50 (more hypothetical crashes)', { exact: true }).waitFor();
    console.log('PASS Compose calculator — evidence and hypothetical arithmetic while the real Overview is gated');
    const credentials = { email: `phase6-${randomUUID()}@example.com`, password: randomUUID() };
    const registration = await page.request.post(`${staging}/api/v1/auth/register`, { data: credentials });
    assert.equal(registration.status(), 201);
    await page.goto(staging);
    await page.locator('input[type=email]').fill(credentials.email);
    await page.locator('input[type=password]').fill(credentials.password);
    await page.locator('button[type=submit]').click();
    await page.getByRole('link', { name: 'Upload Dataset' }).click();
    const upload = page.waitForResponse(response => response.url().endsWith('/datasets/upload'));
    await page.locator('input[type=file]').setInputFiles({
      name: 'phase6-synthetic.csv', mimeType: 'text/csv',
      buffer: Buffer.from('group,value\nA,1\nA,2\nB,4\nB,8\n'),
    });
    assert.equal((await upload).status(), 200);
    await page.getByRole('link', { name: 'Analysis Workspace' }).click();
    const analysis = page.waitForResponse(response => response.url().endsWith('/analysis/execute'));
    await page.getByRole('button', { name: 'Run', exact: true }).first().click();
    const execution = await analysis;
    assert.equal(execution.status(), 200);
    assert.ok((await execution.json()).data.tables.length);
    await page.getByRole('link', { name: 'Report Builder' }).click();
    await page.getByRole('button', { name: 'Generate report' }).click();
    await page.getByText('Report ready.', { exact: true }).waitFor();
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download', exact: true }).click();
    assert.equal((await readFile(await (await download).path())).subarray(0, 4).toString(), '%PDF');
    await page.close();
    console.log('PASS Compose analyser — sign-in, CSV upload, analysis, and PDF report download');
  }
} finally {
  await browser.close();
}
