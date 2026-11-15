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
const provenancePath = '**/api/v1/road-safety/overview/provenance';
const gateDetail = {
  code: 'OVERVIEW_UNAVAILABLE', message: 'The reviewed Road Safety Overview dataset is unavailable.',
  approval_state: null, data: null,
};

async function assertDocument(page) {
  assert.equal(await page.getByRole('main').count(), 1);
  assert.equal(await page.getByRole('heading', { level: 1 }).count(), 1);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
}

async function assertWithheld(page) {
  assert.equal(await page.getByRole('region', { name: 'Crash totals' }).count(), 0);
  assert.equal(await page.locator('a[href*="/downloads/"], img[src*="/assets/"]').count(), 0);
  assert.doesNotMatch(await page.getByRole('main').innerText(), /248,810|238,281|Manifest SHA-256/);
}

async function publicRoutes(size, width) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  if (evidence) await page.context().tracing.start({ screenshots: true, snapshots: true });
  let releaseCheck;
  const hold = new Promise(resolve => { releaseCheck = resolve; });
  const servePending = async route => {
    await hold;
    await route.fulfill({ status: 503, json: { detail: gateDetail } });
  };
  await page.route(provenancePath, servePending);

  await page.goto(fixture);
  await page.getByRole('status').filter({ hasText: 'Checking the release' }).waitFor();
  await assertWithheld(page);
  await page.keyboard.press('Tab');
  assert.equal(await page.getByRole('link', { name: 'Skip to content' }).evaluate(el => el === document.activeElement), true);
  await page.keyboard.press('Enter');
  assert.equal(await page.getByRole('main').evaluate(el => el === document.activeElement), true);
  releaseCheck();
  await page.getByRole('heading', { name: 'Reviewed findings unavailable' }).waitFor();
  await assertDocument(page);
  await assertWithheld(page);
  const navigation = page.getByRole('navigation', { name: 'Main navigation' });
  for (const [name, href] of [['Methods', '/methods'], ['What-if calculator', '/illustrative-scenario'], ['Dataset analyser', '/analyser']]) {
    assert.equal(await navigation.getByRole('link', { name, exact: true }).getAttribute('href'), href);
  }
  const accessibility = await page.getByRole('main').ariaSnapshot();
  assert.match(accessibility, /status:[\s\S]*Reviewed findings unavailable[\s\S]*Read the Methods/);
  await screenshot(page, `public-index-pending-${size}`);
  await page.getByRole('link', { name: 'Which reports can be mapped' }).click();
  const mapping = page.getByRole('heading', { name: 'Why the map covers fewer reports' });
  await mapping.waitFor();
  await page.waitForFunction(() => document.activeElement?.id === 'mapping');
  await page.reload();
  await mapping.waitFor();
  await assertDocument(page);
  await screenshot(page, `public-methods-${size}`);
  await page.goBack();
  await page.getByRole('link', { name: 'Open the crash record' }).waitFor();
  await page.goForward();
  await mapping.waitFor();

  await page.goto(`${fixture}/road-safety`);
  await page.getByRole('heading', { name: 'Reviewed findings unavailable' }).waitFor();
  await assertDocument(page);
  await assertWithheld(page);
  await screenshot(page, `public-record-unavailable-${size}`);

  await page.unroute(provenancePath, servePending);
  const offline = route => route.abort('internetdisconnected');
  await page.route(provenancePath, offline);
  await page.getByRole('button', { name: 'Retry release check' }).click();
  await page.getByRole('heading', { name: 'Could not check the findings' }).waitFor();
  await assertWithheld(page);
  await screenshot(page, `public-record-transport-${size}`);
  await page.unroute(provenancePath, offline);
  if (size === 'tablet') {
    let finish;
    const wait = new Promise(resolve => { finish = resolve; });
    const timeout = async route => {
      await wait;
      await route.abort().catch(() => {});
    };
    await page.route(provenancePath, timeout);
    await page.getByRole('button', { name: 'Retry release check' }).click();
    await page.getByRole('status').filter({ hasText: 'Checking the release' }).waitFor();
    try {
      await page.getByRole('heading', { name: 'Could not check the findings' }).waitFor({ timeout: 18000 });
      await assertWithheld(page);
    } finally {
      finish();
      await page.unroute(provenancePath, timeout);
    }
  }
  const tablePath = '**/api/v1/road-safety/overview/tables/county_periods';
  const mix = async route => {
    const response = await route.fetch();
    const json = await response.json();
    json.data.bundle.manifest_sha256 = '0'.repeat(64);
    await route.fulfill({ response, json });
  };
  await page.route(tablePath, mix);
  await page.getByRole('button', { name: 'Retry release check' }).click();
  await page.getByRole('heading', { name: 'Could not check the findings' }).waitFor();
  await assertWithheld(page);
  await page.unroute(tablePath, mix);
  await page.getByRole('button', { name: 'Retry release check' }).click();
  await page.getByText('Synthetic test fixture. Counts are invented for verification.').waitFor();

  // Exercise 200% CSS zoom at the intermediate width.
  if (width === 768) {
    await page.goto(`${fixture}/methods`);
    await page.addStyleTag({ content: 'body { zoom: 2; }' });
    await assertDocument(page);
    await screenshot(page, 'public-methods-200-percent');
  }
  if (evidence) await page.context().tracing.stop({ path: `${evidence}/public-${size}.zip` });
  await page.close();
  console.log(`PASS ${size} ${width}px — public routes, slow check, unavailable, transport, mixed identity and retry`);
}

try {
  for (const [size, width] of Object.entries({ ...widths, tablet: 768 })) await publicRoutes(size, width);
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
    await page.waitForFunction(() => document.querySelectorAll('.js-plotly-plot').length === 3);
    const gridCsv = await page.request.get(new URL(await page.getByRole('link', { name: 'Download grid cell counts (CSV)' }).getAttribute('href'), fixture).href);
    assert.equal(gridCsv.status(), 200);
    assert.match(gridCsv.headers()['x-artifact-sha256'], /^[0-9a-f]{64}$/);
    assert.match(await gridCsv.text(), /mapped_crashes/);

    // --- Phase 7B Verification: Annual slice, year control, coverage, URL sync, and CSV ---
    const yearSelect = page.getByLabel('Select observation year');
    await yearSelect.waitFor();
    assert.equal(await yearSelect.inputValue(), '2024');

    const coverage = page.getByTestId('selected-year-coverage');
    await coverage.waitFor();
    assert.match(await coverage.innerText(), /Selected Year: 2024/);
    assert.match(await coverage.innerText(), /Examining 12 police-reported crashes/);
    assert.match(await coverage.innerText(), /LOW_2024_HOUR_COVERAGE/);
    assert.match(await coverage.innerText(), /Observed zero \(NO_2024_ILLUMINATION_COVERAGE\)/);
    assert.match(await coverage.innerText(), /Serious or fatal crashes \(codes 1 & 2\):\s*2/);
    assert.match(await coverage.innerText(), /Zero accepted road-site assignments/);
    assert.match(await coverage.innerText(), /Travel exposure and traffic volumes are unmeasured/);
    assert.match(await coverage.innerText(), /Supports no inference regarding per-trip risk/);

    // Change year to 2015 and verify coverage details and URL sync
    await yearSelect.selectOption('2015');
    await page.waitForFunction(() => new URL(window.location.href).searchParams.get('year') === '2015');
    assert.match(await coverage.innerText(), /Selected Year: 2015/);
    assert.match(await coverage.innerText(), /Unavailable[\s\S]*SEVERITY_CODING_BREAK_2016/);
    assert.match(await coverage.innerText(), /Populated illumination:[\s\S]*11\s*\/\s*12/);
    assert.match(await coverage.innerText(), /Valid hour of day:[\s\S]*10\s*\/\s*12/);

    // Verify row selection state in table
    const row2015 = annual.getByRole('row', { name: /^2015/ });
    assert.equal(await row2015.getAttribute('aria-selected'), 'true');

    // Click 2024 row in table to select it
    const row2024 = annual.getByRole('row', { name: /^2024/ });
    await row2024.click();
    await page.waitForFunction(() => new URL(window.location.href).searchParams.get('year') === '2024');
    assert.equal(await yearSelect.inputValue(), '2024');

    // Verify direct link with parameter and invalid year fallback
    await page.goto(`${fixture}/road-safety?year=2015`);
    await yearSelect.waitFor();
    assert.equal(await yearSelect.inputValue(), '2015');
    await page.goto(`${fixture}/road-safety?year=9999`);
    await yearSelect.waitFor();
    assert.equal(await yearSelect.inputValue(), '2024');
    await page.goBack();
    await page.waitForFunction(() => document.querySelector('#annual-year-select')?.value === '2015');

    // Verify verified CSV export for annual series
    const annualCsv = await page.request.get(new URL(await page.getByRole('link', { name: 'Download complete annual series (county_periods.csv)' }).getAttribute('href'), fixture).href);
    assert.equal(annualCsv.status(), 200);
    assert.match(annualCsv.headers()['x-artifact-sha256'], /^[0-9a-f]{64}$/);
    assert.match(annualCsv.headers()['x-manifest-sha256'], /^[0-9a-f]{64}$/);
    assert.match(await annualCsv.text(), /reported_crashes/);

    // Verify root InvestigationPage displays approved evidence entry when ready
    await page.goto(fixture);
    await page.getByRole('heading', { name: 'What can Allegheny County’s crash reports tell us?' }).waitFor();
    await page.getByRole('heading', { name: 'Annual crash reports in Allegheny County' }).waitFor();
    await page.waitForFunction(() => document.querySelectorAll('.js-plotly-plot').length === 1);
    await page.getByRole('link', { name: 'Open the complete road-safety crash record' }).waitFor();
    await screenshot(page, `fixture-root-ready-${size}`);

    // Return to road-safety page for existing calculator sequence
    await page.goto(`${fixture}/road-safety`);
    await page.getByText('Synthetic test fixture. Counts are invented for verification.').waitFor();

    assert.ok(await page.locator('main').evaluate(element => element.scrollWidth <= element.clientWidth + 1));
    await screenshot(page, `fixture-overview-${size}`);

    const next = page.getByRole('link', { name: 'Open the illustrative scenario workspace' });
    await tabTo(page, next);
    await page.keyboard.press('Enter');
    await page.getByRole('heading', { name: 'What-if calculator', exact: true }).waitFor();
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
      await page.getByRole('heading', { name: 'Reviewed findings unavailable' }).waitFor();
      const response = await page.request.get(`${staging}/api/v1/road-safety/overview/provenance`);
      assert.equal(response.status(), 503);
      assert.deepEqual((await response.json()).detail, gateDetail);
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
    console.log('PASS Pending-release calculator — evidence and hypothetical arithmetic while the real Overview is gated');
    const credentials = { email: `phase6-${randomUUID()}@example.com`, password: randomUUID() };
    const registration = await page.request.post(`${staging}/api/v1/auth/register`, { data: credentials });
    assert.equal(registration.status(), 201);
    await page.goto(`${staging}/upload`);
    await page.getByRole(`heading`, { name: `Dataset analyser` }).waitFor();
    await page.locator('input[type=email]').fill(credentials.email);
    await page.locator('input[type=password]').fill(credentials.password);
    await page.locator('button[type=submit]').click();
    await page.getByRole('link', { name: 'Upload Dataset' }).waitFor();
    assert.equal(new URL(page.url()).pathname, '/upload');
    await page.goto(`${staging}/analyser`);
    await page.getByRole('link', { name: 'Home Workspace' }).waitFor();
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
    await page.getByRole('link', { name: 'Export Centre' }).click();
    const exportReady = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Profile (.json)' }).click();
    assert.ok(JSON.parse(await readFile(await (await exportReady).path(), 'utf8')));
    await page.close();
    console.log('PASS Signed-in analyser — sign-in, CSV upload, analysis, PDF report download and JSON profile export');
  }
} finally {
  await browser.close();
}
