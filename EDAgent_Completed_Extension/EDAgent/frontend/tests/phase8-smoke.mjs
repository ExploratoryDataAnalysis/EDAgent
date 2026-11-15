import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { performance } from 'node:perf_hooks';
const { devices, chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');

const fixture = process.env.FIXTURE_URL || 'http://127.0.0.1:5177';
const staging = process.env.STAGING_URL;
const large = process.env.PHASE8_LARGE_URL;
const ledger = process.env.FIXTURE_LEDGER;
const output = process.env.SMOKE_OUTPUT;
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_EXECUTABLE });
const mapRoute = '/road-safety/map';
const evidenceRoute = '/road-safety/evidence';
const api = '/api/v1/road-safety/overview';
const mapHeading = 'Where are mapped reports concentrated?';
const evidenceHeading = 'How was severity recorded in each era?';
const closed = 'Reviewed findings unavailable';
const error = 'Could not check the findings';
const phase8Shot = (page, name) => output && page.screenshot({ path: `${output}/${name}.png`, fullPage: true });

async function assertReflow(page) {
  assert.equal(await page.getByRole('heading', { level: 1 }).count(), 1);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
}

async function keyboardReach(page, locator) {
  for (let i = 0; i < 40; i++) {
    if (await locator.evaluate(el => el === document.activeElement)) return;
    await page.keyboard.press('Tab');
  }
  assert.fail('Could not reach the control via Tab');
}

async function checkArtifact(page, name, marker) {
  const href = await page.getByRole('link', { name, exact: true }).getAttribute('href');
  const url = new URL(href, page.url());
  const pin = url.searchParams.get('manifest_sha256');
  assert.match(pin, /^[a-f0-9]{64}$/);
  const response = await page.request.get(url.href);
  assert.equal(response.status(), 200);
  assert.equal(response.headers()['x-manifest-sha256'], pin);
  assert.match(await response.text(), marker);
}

async function assertClosed(page, heading = closed) {
  await page.getByRole('heading', { name: heading }).waitFor();
  assert.equal(await page.locator('canvas, img, figure, a[href*="/downloads/"]').count(), 0);
  await page.getByRole('link', { name: 'Read the Methods' }).waitFor();
  await page.getByRole('link', { name: 'Road Safety Overview' }).waitFor();
}

try {
  if (output) await mkdir(output, { recursive: true });
  for (const width of [390, 768, 1440]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.goto(fixture + mapRoute);
    await page.getByRole('heading', { name: mapHeading }).waitFor();
    assert.match(await page.locator('figure').innerText(), /20 of 24 reports \(83\.33%\).*1 occupied cell/);
    const cellId = page.getByRole('textbox', { name: 'Cell ID' });
    await keyboardReach(page, cellId);
    await page.keyboard.type('-80.000:40.450');
    await page.keyboard.press('Enter');
    const selected = page.getByRole('region', { name: 'Selected grid cell' });
    await selected.waitFor();
    assert.match(await selected.innerText(), /-80\.000:40\.450\s+20/);
    assert.match(await page.locator('[aria-live="polite"]').first().innerText(), /20 mapped reports \(20–49 reports band\)/);
    await page.getByText('Occupied cell table', { exact: true }).click();
    const browse = page.getByRole('button', { name: '-80.000:40.450' });
    await browse.waitFor();
    assert.equal(await browse.getAttribute('aria-pressed'), 'true');
    await checkArtifact(page, 'All occupied cells (CSV)', /40\.45,-80,20,2/);
    await assertReflow(page);
    await phase8Shot(page, `map-ready-${width}`);

    if (width === 390) {
      await page.getByRole('button', { name: 'Zoom to selected cell' }).click();
      const pixels = await page.locator('canvas').evaluate(canvas => {
        const ctx = canvas.getContext('2d');
        const pixel = offset => [...ctx.getImageData(canvas.width * (0.5 + offset / 0.03), canvas.height / 2, 1, 1).data];
        return [pixel(-0.00035), pixel(0.00035)];
      });
      assert.deepEqual(pixels, [[20, 93, 87, 255], [0, 0, 0, 0]]);
      await cellId.fill('-80.000:40.451');
      await cellId.press('Enter');
      await page.getByText(/No occupied cell appears.*count is unavailable/).waitFor();
      const canvas = page.locator('canvas');
      const bounds = await canvas.boundingBox();
      await canvas.click({ position: { x: bounds.width * 0.49, y: bounds.height / 2 } });
      await selected.waitFor();
      assert.match(await selected.innerText(), /-80\.000:40\.450\s+20/);
    }
    await page.reload();
    await cellId.waitFor();

    await page.goto(fixture + evidenceRoute);
    await page.getByRole('heading', { name: evidenceHeading }).waitFor();
    const oldEra = page.getByRole('region', { name: '2004–2015', exact: true });
    const modern = page.getByRole('region', { name: '2016–2024', exact: true });
    assert.match(await oldEra.innerText(), /9 of 12.*known severity[\s\S]*3 reports are excluded[\s\S]*unavailable for this era/);
    assert.match(await modern.innerText(), /2 of 9 known-severity reports \(22\.22%\)/);
    assert.match(await modern.getByRole('row', { name: /Missing severity/ }).innerText(), /0\s+12 all reports\s+0\.00%/);
    const coverage = page.getByRole('region', { name: '2024 measurement coverage' });
    assert.match(await coverage.innerText(), /Valid hour\s+1\s+11\s+12\s+8\.33%/);
    assert.match(await coverage.innerText(), /Populated illumination\s+0\s+12\s+12\s+0\.00%/);
    const association = page.getByRole('region', { name: 'Severity associations' });
    const associationRows = association.getByRole('row');
    assert.match(await associationRows.nth(1).innerText(), /Collision type[\s\S]*0\.4500[\s\S]*Unknown, Backing[\s\S]*numerical underflow/);
    assert.match(await associationRows.nth(2).innerText(), /Time period[\s\S]*None[\s\S]*1\.250e-1/);
    const fields = page.getByRole('combobox', { name: 'Source field' });
    await keyboardReach(page, fields);
    await page.keyboard.press('ArrowDown');
    assert.equal(await fields.inputValue(), 'ILLUMINATION');
    assert.match(await page.getByRole('region', { name: 'Selected source field missingness' }).innerText(), /ILLUMINATION\s+13\s+24\s+54\.17%/);
    await checkArtifact(page, 'Severity association tests (CSV)', /COLLISION_LABEL,2016,2023,7,7,10,2,,True,"Unknown, Backing",1\.5,0\.45/);
    await assertReflow(page);
    await phase8Shot(page, `evidence-ready-${width}`);
    await page.reload();
    await fields.waitFor();
    if (width === 768) {
      for (const [route, heading] of [[mapRoute, mapHeading], [evidenceRoute, evidenceHeading]]) {
        await page.goto(fixture + route);
        await page.getByRole('heading', { name: heading }).waitFor();
        await page.evaluate(() => { document.body.style.zoom = '2'; });
        await assertReflow(page);
        await phase8Shot(page, `reflow-${route.split('/').at(-1)}-200`);
      }
    }

    if (staging) {
      for (const route of [mapRoute, evidenceRoute]) {
        await page.goto(staging + route);
        await assertClosed(page);
        await assertReflow(page);
        await phase8Shot(page, `${route.split('/').at(-1)}-candidate-gated-${width}`);
      }
    }
    await page.close();
  }

  for (const width of [390, 1440]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.addInitScript(() => {
      const native = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (type, ...args) {
        return type === '2d' ? null : native.call(this, type, ...args);
      };
    });
    await page.goto(fixture + mapRoute);
    await page.getByText('Interactive map unavailable.', { exact: false }).waitFor();
    await page.waitForFunction(() => document.querySelector('figure img')?.naturalWidth > 0);
    await page.getByRole('button', { name: '-80.000:40.450' }).click();
    assert.match(await page.getByRole('region', { name: 'Selected grid cell' }).innerText(), /20/);
    await assertReflow(page);
    await phase8Shot(page, `map-renderer-fallback-${width}`);
    if (width === 390 && ledger) {
      const original = await readFile(ledger, 'utf8');
      const withdrawn = JSON.parse(original);
      withdrawn.descriptive_release.decision = 'WITHDRAWN';
      try {
        await writeFile(ledger, JSON.stringify(withdrawn));
        await page.evaluate(() => window.dispatchEvent(new Event('focus')));
        await assertClosed(page);
      } finally {
        await writeFile(ledger, original);
      }
      await page.getByRole('button', { name: 'Retry release check' }).click();
      await page.getByRole('heading', { name: mapHeading }).waitFor();
    }
    await page.close();
  }

  const page = await browser.newPage();
  const broken = route => route.abort();
  await page.route(`**${api}/provenance`, broken);
  await page.goto(fixture + evidenceRoute);
  await assertClosed(page, error);
  await page.unroute(`**${api}/provenance`, broken);
  const mixed = async route => {
    const response = await route.fetch();
    const result = await response.json();
    result.data.bundle.manifest_sha256 = '0'.repeat(64);
    await route.fulfill({ response, json: result });
  };
  await page.route(`**${api}/tables/severity_associations`, mixed);
  await page.getByRole('button', { name: 'Retry release check' }).click();
  await assertClosed(page, error);
  await page.unroute(`**${api}/tables/severity_associations`, mixed);
  await page.getByRole('button', { name: 'Retry release check' }).click();
  await page.getByRole('heading', { name: evidenceHeading }).waitFor();
  let releaseLate;
  let requestStarted;
  const late = new Promise(resolve => { releaseLate = resolve; });
  const started = new Promise(resolve => { requestStarted = resolve; });
  await page.route(`**${api}/tables/severity_associations`, async route => {
    requestStarted();
    await late;
    await route.continue().catch(() => {});
  });
  await page.reload();
  await started;
  await page.getByRole('link', { name: 'Road Safety Overview' }).click();
  await page.getByRole('link', { name: 'County crash grid' }).click();
  await page.getByRole('heading', { name: mapHeading }).waitFor();
  releaseLate();
  assert.equal(await page.getByRole('heading', { name: evidenceHeading }).count(), 0);
  await page.close();

  if (large) {
    const context = await browser.newContext({ ...devices['Pixel 7'], viewport: { width: 390, height: 844 } });
    const phone = await context.newPage();
    const cdp = await context.newCDPSession(phone);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
    await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 70,
      downloadThroughput: 12_500_000 / 8, uploadThroughput: 2_000_000 / 8 });
    const samples = [];
    for (let i = 0; i < 3; i++) {
      const start = performance.now();
      await phone.goto(large + mapRoute, { waitUntil: 'domcontentloaded', timeout: 60000 });
      await phone.getByRole('heading', { name: mapHeading }).waitFor();
      await phone.locator('canvas').evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const startup = Math.round(performance.now() - start);
      assert.match(await phone.locator('figure').innerText(), /38,332 occupied cells/);
      await phone.getByRole('textbox', { name: 'Cell ID' }).fill('-80.199:40.201');
      const selectTime = await phone.getByRole('textbox', { name: 'Cell ID' }).evaluate(async input => {
        const started = performance.now();
        input.form.requestSubmit();
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        return Math.round(performance.now() - started);
      });
      await phone.getByRole('region', { name: 'Selected grid cell' }).waitFor();
      samples.push({ startup, selectTime });
    }
    console.log('Large synthetic phone profile (ms):', JSON.stringify(samples));
    await phone.goto(large + evidenceRoute);
    await phone.getByText('2024 coverage unavailable.', { exact: true }).waitFor();
    assert.match(await phone.getByRole('region', { name: '2024 measurement coverage' }).innerText(), /Populated illumination\s+Unavailable/);
    await assertReflow(phone);
    await phase8Shot(phone, 'evidence-partial-390');
    await context.close();
  }
  console.log('PASS Phase 8 map, severity, release integrity and responsive browser checks');
} finally {
  await browser.close();
}
