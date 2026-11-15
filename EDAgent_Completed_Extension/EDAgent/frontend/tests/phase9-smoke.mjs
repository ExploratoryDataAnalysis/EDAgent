import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.STAGING_URL || 'http://127.0.0.1:5178';
const output = process.env.SMOKE_OUTPUT;
const scenarioPath = '/api/v1/interventions/scenarios';
const scenarioRoute = '**' + scenarioPath;
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_EXECUTABLE });

async function tabTo(page, target) {
  for (let step = 0; step < 20; step++) {
    if (await target.evaluate(element => element === document.activeElement)) return;
    await page.keyboard.press('Tab');
  }
  assert.fail('Control could not be reached with Tab');
}

// Hold one real API response while subsequent requests go straight to the server.
async function holdScenario(page) {
  let received;
  let release;
  let delivered;
  const ready = new Promise(resolve => { received = resolve; });
  const hold = new Promise(resolve => { release = resolve; });
  const done = new Promise(resolve => { delivered = resolve; });
  await page.route(scenarioRoute, async route => {
    const response = await route.fetch();
    received(response.status());
    await hold;
    await route.fulfill({ response }).catch(() => {});
    delivered();
  }, { times: 1 });
  return {
    ready,
    async finish() {
      release();
      await done;
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    },
  };
}

try {
  if (output) await mkdir(output, { recursive: true });
  for (const width of [390, 1440]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    const shot = state => output && page.screenshot({ path: output + '/' + state + '-' + width + '.png', fullPage: true });
    const main = page.getByRole('main');
    const example = page.getByRole('button', { name: 'Run an invented example' });
    const calculate = page.getByRole('button', { name: 'Calculate scenario' });
    const reset = page.getByRole('button', { name: 'Reset inputs' });
    const crashType = page.getByLabel('Shared crash type', { exact: true });
    const years = page.getByLabel('Analysis period (years)', { exact: true });
    const baseline = page.getByLabel('Hypothetical baseline crash count', { exact: true });
    const factor = page.getByLabel('Hypothetical CMF', { exact: true });
    const lower = page.getByLabel('Lower factor', { exact: true });
    const upper = page.getByLabel('Upper factor', { exact: true });
    const result = page.getByRole('region', { name: 'Hypothetical results' });
    const status = page.getByRole('status').filter({ has: result });
    const alert = main.getByRole('alert').first();

    await page.goto(base);
    await page.getByRole('heading', { name: 'Reviewed findings unavailable' }).waitFor();
    const gate = await page.request.get(base + '/api/v1/road-safety/overview/provenance');
    assert.equal(gate.status(), 503);
    assert.equal((await gate.json()).detail.code, 'OVERVIEW_UNAVAILABLE');
    const nav = page.getByRole('navigation', { name: 'Main navigation' });
    await nav.getByRole('link', { name: 'Methods' }).click();
    await page.getByRole('heading', { name: 'Why the map covers fewer reports' }).waitFor();
    await nav.getByRole('link', { name: 'What-if calculator' }).click();
    await page.getByText('Hypothetical scenario', { exact: true }).waitFor();

    const references = page.getByRole('region', { name: 'Treatment references' });
    const select = references.getByLabel('Select a treatment reference');
    await select.getByRole('option', { name: 'Roadway lighting' }).waitFor({ state: 'attached' });
    assert.equal(await select.getByRole('option').count(), 7);
    assert.equal(await result.count(), 0);
    assert.equal(await baseline.inputValue(), '');
    assert.ok(await example.evaluate(element => element.getBoundingClientRect().bottom <= window.innerHeight));
    await shot('initial');

    await tabTo(page, example);
    assert.equal(await example.evaluate(element => getComputedStyle(element).outlineWidth), '2px');
    const sent = page.waitForRequest(request => request.url().endsWith(scenarioPath) && request.method() === 'POST');
    await page.keyboard.press('Enter');
    assert.deepEqual((await sent).postDataJSON(), {
      schema_version: '1', scenario_kind: 'HYPOTHETICAL', hypothetical_baseline_n: '40',
      crash_type: 'ALL', analysis_period: { length: 5, unit: 'YEARS' }, units: 'CRASHES_PER_ANALYSIS_PERIOD',
      cmf: { origin: 'USER_ENTERED_HYPOTHETICAL', crash_type: 'ALL', value: '0.80', bounds: { lower: '0.70', upper: '0.95' } },
    });
    await result.waitFor();
    assert.equal(await status.getAttribute('aria-atomic'), 'true');
    assert.match(await status.ariaSnapshot(), /status:[\s\S]+32\.00 hypothetical crashes over 5 years[\s\S]+8\.00 \(fewer hypothetical crashes\)[\s\S]+28\.00 to 38\.00[\s\S]+no statistical confidence level/);
    assert.equal(await example.evaluate(element => element === document.activeElement), true);
    assert.ok(await result.evaluate(element => element.getBoundingClientRect().top < window.innerHeight));
    assert.deepEqual(await Promise.all([years, baseline, factor, lower, upper].map(field => field.inputValue())),
      ['5', '40', '0.80', '0.70', '0.95']);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await shot('result');

    for (const control of [crashType, years, baseline, factor, lower, upper, calculate, reset]) {
      await page.keyboard.press('Tab');
      assert.equal(await control.evaluate(element => element === document.activeElement), true);
    }
    await select.selectOption('lighting');
    await references.getByText('REFERENCE_ONLY', { exact: true }).waitFor();
    assert.equal(await references.getByRole('link').count(), 2);
    assert.equal(await result.count(), 1);

    await factor.fill('0..8');
    assert.equal(await result.count(), 0);
    await calculate.click();
    await alert.filter({ hasText: 'Enter a positive decimal' }).waitFor();
    assert.equal(await factor.getAttribute('aria-invalid'), 'true');
    assert.match(await factor.getAttribute('aria-describedby'), /factor-error/);
    assert.match(await alert.ariaSnapshot(), /alert:[\s\S]+Check the highlighted inputs/);
    await shot('error');
    await factor.fill('0.80');
    await upper.fill('0.60');
    await calculate.click();
    await alert.filter({ hasText: 'Set the lower factor at or below your CMF' }).waitFor();
    assert.match(await upper.getAttribute('aria-describedby'), /bounds-error/);
    await upper.fill('0.95');
    await calculate.click();
    await result.waitFor();
    assert.equal(await upper.getAttribute('aria-invalid'), null);

    await page.route(scenarioRoute, route => route.continue({
      postData: { ...route.request().postDataJSON(), site_id: 'Invented QA site' },
    }), { times: 1 });
    const refused = page.waitForResponse(response => response.url().endsWith(scenarioPath));
    await calculate.click();
    const refusal = await refused;
    assert.equal(refusal.status(), 503);
    assert.equal('data' in await refusal.json(), false);
    await alert.filter({ hasText: 'REAL_SITE_BENEFIT_UNAVAILABLE' }).waitFor();
    assert.equal(await result.count(), 0);
    await shot('refusal');

    for (const action of [() => crashType.selectOption('PEDESTRIAN'), () => reset.click()]) {
      const pending = await holdScenario(page);
      await example.click();
      await page.getByText('Calculating hypothetical results…').waitFor();
      assert.equal(await pending.ready, 200);
      await action();
      await pending.finish();
      assert.equal(await result.count(), 0);
    }
    assert.equal(await baseline.inputValue(), '');
    assert.equal(await crashType.inputValue(), 'ALL');

    const pending = await holdScenario(page);
    await example.click();
    await page.getByText('Calculating hypothetical results…').waitFor();
    assert.equal(await pending.ready, 200);
    await lower.fill('');
    await upper.fill('');
    await factor.fill('1.25');
    await calculate.click();
    await result.getByText('-10.00 (more hypothetical crashes)', { exact: true }).waitFor();
    await pending.finish();
    assert.match(await result.innerText(), /50\.00 hypothetical crashes/);
    assert.doesNotMatch(await result.innerText(), /32\.00|sensitivity range/);

    await page.route(scenarioRoute, route => route.abort('internetdisconnected'), { times: 1 });
    await factor.fill('1');
    await calculate.click();
    await alert.filter({ hasText: 'Your inputs are still here' }).waitFor();
    assert.equal(await result.count(), 0);
    assert.equal(await baseline.inputValue(), '40');
    assert.equal(await factor.inputValue(), '1');
    await page.getByRole('button', { name: 'Retry calculation' }).click();
    await result.getByText('0.00 (no change)', { exact: true }).waitFor();
    await baseline.fill('0');
    await factor.fill('1.25');
    await calculate.click();
    await result.getByText(/0\.00 hypothetical crashes over 5 years/).waitFor();
    await result.getByText('0.00 (no change)', { exact: true }).waitFor();
    await page.getByRole('link', { name: 'View hypothetical results' }).click();
    assert.equal(await result.getByRole('heading', { level: 2 }).evaluate(el => el === document.activeElement), true);
    await page.close();
    console.log('PASS ' + width + 'px — D7 gate, Methods, example, keyboard and live regions, field corrections, refusal, edit/reset, response order and retry');
  }
} finally {
  await browser.close();
}
