import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, stat, mkdir } from 'node:fs/promises';
import { resolve, extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const frontendDir = resolve(__dirname, '..');
const distDir = resolve(frontendDir, 'dist');
const repoRoot = resolve(frontendDir, '..', '..', '..');
const candidateDir = resolve(repoRoot, 'data', 'exports', 'models', 'candidate');
const screenshotsDir = resolve(repoRoot, '.repro', 'phase12c', 'screenshots');

await mkdir(screenshotsDir, { recursive: true });

// Load candidate JSON data from disk
const manifest = JSON.parse(await readFile(join(candidateDir, 'manifest.json'), 'utf-8'));
const modelComparisons = JSON.parse(await readFile(join(candidateDir, 'model_comparisons.json'), 'utf-8'));
const featureAblation = JSON.parse(await readFile(join(candidateDir, 'feature_ablation.json'), 'utf-8'));
const thresholdPerformance = JSON.parse(await readFile(join(candidateDir, 'threshold_performance.json'), 'utf-8'));
const calibrationDiagnostics = JSON.parse(await readFile(join(candidateDir, 'calibration_diagnostics.json'), 'utf-8'));

const mimeTypes = {
  '.html': 'text/html',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.woff2': 'font/woff2',
};

// Start static file server for frontend build
const server = createServer(async (req, res) => {
  const urlPath = req.url.split('?')[0];
  let filePath = resolve(distDir, '.' + urlPath);
  try {
    const fileStat = await stat(filePath);
    if (fileStat.isDirectory()) filePath = resolve(distDir, 'index.html');
  } catch {
    filePath = resolve(distDir, 'index.html');
  }
  try {
    const content = await readFile(filePath);
    res.writeHead(200, { 'Content-Type': mimeTypes[extname(filePath)] || 'text/html' });
    res.end(content);
  } catch (err) {
    const fallback = await readFile(resolve(distDir, 'index.html'));
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(fallback);
  }
});

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const port = server.address().port;
const baseUrl = `http://127.0.0.1:${port}`;
console.log(`Static server running at ${baseUrl}`);

const { chromium } = await import('playwright');
const chromePath = process.env.CHROMIUM_EXECUTABLE || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const browser = await chromium.launch({ executablePath: chromePath, headless: true });

try {
  // TEST 1: Gated / Offline State
  console.log('Testing Gated / Offline State...');
  {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.route('**/api/v1/road-safety/models/provenance', async (route) => {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        headers: { 'Cache-Control': 'no-store' },
        body: JSON.stringify({
          detail: {
            code: 'MODELS_UNAVAILABLE',
            message: 'The reviewed Retrospective Severity Models dataset is unavailable.',
            approval_state: null,
            data: null,
          },
        }),
      });
    });

    await page.goto(`${baseUrl}/road-safety/models`, { waitUntil: 'networkidle' });

    // Assertions for gated view
    const mainText = (await page.getByRole('main').innerText()).toLowerCase();
    assert.ok(mainText.includes('retrospective model diagnostics are offline'), 'Must show offline title');
    assert.ok(mainText.includes('pending independent approval'), 'Must show pending notice');
    assert.ok(mainText.includes('review_candidate'), 'Must cite REVIEW_CANDIDATE status');
    assert.ok(mainText.includes('primary_site_assignments_accepted: 0'), 'Must cite 0 accepted site assignments');

    // Screenshot
    const screenshotPath = join(screenshotsDir, 'desktop_1440_gated_offline.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`Saved screenshot: ${screenshotPath}`);
    await page.close();
  }

  // TEST 2: Approved State across Viewports
  const viewports = [
    { name: 'desktop_1440', width: 1440, height: 900 },
    { name: 'tablet_768', width: 768, height: 1024 },
    { name: 'mobile_390', width: 390, height: 844 },
  ];

  for (const vp of viewports) {
    console.log(`Testing Approved State on ${vp.name} (${vp.width}x${vp.height})...`);
    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
    page.on('console', msg => console.log(`[${vp.name} BROWSER]`, msg.text()));
    page.on('pageerror', err => console.log(`[${vp.name} BROWSER ERROR]`, err));
    page.on('request', req => console.log(`[${vp.name} REQ]`, req.method(), req.url()));

    // Mock API routes to return candidate derivative
    await page.route('**/api/v1/road-safety/models/provenance', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: { 'Cache-Control': 'no-store' },
        body: JSON.stringify({
          success: true,
          data: {
            schema_version: 1,
            run_id: manifest.run_id,
            sources: manifest.inputs,
            bundle: {
              kind: manifest.kind,
              version: manifest.version,
              manifest_sha256: '443344dc7fc8cc5d002a7754a13a08b0c666c4ac4d45c2fa13739f4390a0cd46',
              approval_state: 'APPROVED_SEVERITY_MODELS_RELEASE',
            },
            scope: manifest.scope,
            manifest_status: manifest.status,
            tables: manifest.tables,
            outputs: manifest.outputs,
          },
        }),
      });
    });

    await page.route('**/api/v1/road-safety/models/tables/model_comparisons', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { table_id: 'model_comparisons', rows: modelComparisons } }),
      });
    });

    await page.route('**/api/v1/road-safety/models/tables/feature_ablation', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { table_id: 'feature_ablation', rows: featureAblation } }),
      });
    });

    await page.route('**/api/v1/road-safety/models/tables/threshold_performance', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { table_id: 'threshold_performance', rows: thresholdPerformance } }),
      });
    });

    await page.route('**/api/v1/road-safety/models/tables/calibration_diagnostics', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: { table_id: 'calibration_diagnostics', rows: calibrationDiagnostics } }),
      });
    });

    await page.goto(`${baseUrl}/road-safety/models`, { waitUntil: 'networkidle' });

    // Validate 7 mandatory sections
    const mainText = await page.getByRole('main').innerText();

    // Section 1: Research Question & Conditioning
    assert.ok(mainText.includes('1. Target Definition & Conditioning Statement'), 'Section 1 missing');
    assert.ok(mainText.includes('P(Severe Injury | Crash Reported ∧ Severity Known)'), 'Conditioning formula missing');

    // Section 2: Population, Era & Exclusions
    assert.ok(mainText.includes('2. Population, Reporting Era & Exclusions'), 'Section 2 missing');
    assert.ok(mainText.includes('58,660'), 'Training cohort count missing');
    assert.ok(mainText.includes('27,697'), 'Test holdout count missing');
    assert.ok(mainText.includes('43,266'), 'Unknown severity exclusion count missing');

    // Section 3: Model Performance Matrix
    assert.ok(mainText.includes('3. Model Performance on Chronological Holdout'), 'Section 3 missing');
    assert.ok(mainText.includes('HistGradientBoosting + collision'), 'HGB model missing');
    assert.ok(mainText.includes('0.1548'), 'HGB AP 0.1548 missing');
    assert.ok(mainText.includes('0.0444'), 'Chance AP 0.0444 missing');

    // Section 4: Feature Timing & Ablation
    assert.ok(mainText.includes('4. Feature Timing & Collision-Type Ablation'), 'Section 4 missing');
    assert.ok(mainText.includes('0.2020'), 'Collision Cramér V missing');
    assert.ok(mainText.includes('0.0517'), 'RF without collision AP 0.0517 missing');

    // Section 5: Calibration & Decision Thresholds
    assert.ok(mainText.includes('5. Probability Calibration & Decision Thresholds'), 'Section 5 missing');
    assert.ok(mainText.includes('0.0416'), 'Calibrated Brier score 0.0416 missing');
    assert.ok(mainText.includes('0.2132'), 'Uncalibrated Brier score 0.2132 missing');

    // Section 6: Limitations & Prohibited Uses
    assert.ok(mainText.includes('6. Scientific Limitations & Prohibited Uses'), 'Section 6 missing');
    assert.ok(mainText.includes('NO Live Crash Forecasting'), 'Limitation 1 missing');
    assert.ok(mainText.includes('NO Site-Level Risk Scores'), 'Limitation 2 missing');
    assert.ok(mainText.includes('NO Intersection Rankings'), 'Limitation 3 missing');

    // Section 7: Provenance & Downloads
    assert.ok(mainText.includes('7. Provenance, Cryptographic Verification & Downloads'), 'Section 7 missing');
    assert.ok(mainText.includes('443344dc7fc8cc5d002a7754a13a08b0c666c4ac4d45c2fa13739f4390a0cd46'), 'Manifest SHA missing');

    // Responsive layout check: No horizontal overflow
    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth + 1;
    });
    assert.equal(hasHorizontalOverflow, false, `Horizontal overflow detected on viewport ${vp.name}`);

    // Screenshot
    const screenshotPath = join(screenshotsDir, `${vp.name}_approved.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`Saved screenshot: ${screenshotPath}`);

    await page.close();
  }

  console.log('All smoke tests and screenshots completed successfully!');
} finally {
  await browser.close();
  server.close();
}
