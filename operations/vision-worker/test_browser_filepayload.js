'use strict';

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { EventEmitter } = require('events');

const OPT_IN = '--local-browser-file-input';
const EXPECTED_CASES = {
  'public-safe': {
    approvalKind: 'public_safe',
    sha256: '3956f8ed4074e3ab3531a9a821159a65a8a12441e6e5328021d6a09914dd3206',
    size: 2087,
  },
  'locally-redacted': {
    approvalKind: 'locally_redacted',
    sha256: '7a89cb69ae2d29bdb1f8f2311177cb128b877b75f00c6b2a94b33661631b431c',
    forbiddenOriginalSha256: '3022375f32d5bd91bbb890b67b190f23a77b7f6baf1bf68243af44dc628a99b3',
    size: 4688,
  },
};

function argument(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) throw new Error(`MISSING_ARGUMENT:${name}`);
  return path.resolve(process.argv[index + 1]);
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function requireContained(root, target, label) {
  const relative = path.relative(root, target);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error(`${label}_OUTSIDE_ROOT`);
  }
}

function fakeChild() {
  const child = new EventEmitter();
  child.kill = () => {};
  return child;
}

function inspectCase(caseRoot, label) {
  const expected = EXPECTED_CASES[label];
  const request = JSON.parse(fs.readFileSync(path.join(caseRoot, 'request.json'), 'utf8'));
  const approval = JSON.parse(fs.readFileSync(path.join(caseRoot, 'approval.json'), 'utf8'));
  assert.strictEqual(approval.label, label);
  assert.strictEqual(approval.approval_kind, expected.approvalKind);
  assert.strictEqual(request.sources.length, 1);
  assert.strictEqual(request.sources[0].source_ref, 'S1');
  assert.strictEqual(request.sources[0].sha256, expected.sha256);
  assert.strictEqual(approval.final_sha256.S1, expected.sha256);
  const incoming = path.join(caseRoot, 'spool', request.sources[0].incoming_relative_path);
  const bytes = fs.readFileSync(incoming);
  assert.strictEqual(bytes.length, expected.size);
  assert.strictEqual(sha256(bytes), expected.sha256);
  if (expected.forbiddenOriginalSha256) {
    assert.strictEqual(approval.forbidden_original_sha256, expected.forbiddenOriginalSha256);
    assert.notStrictEqual(sha256(bytes), expected.forbiddenOriginalSha256);
  }
  return { request, approval, incoming, bytes };
}

function prepareScenario(chainRoot, evidenceRoot, label, scenario) {
  const sourceCase = path.join(chainRoot, label);
  const scenarioRoot = path.join(evidenceRoot, 'work', scenario);
  requireContained(evidenceRoot, scenarioRoot, 'SCENARIO');
  if (fs.existsSync(scenarioRoot)) throw new Error(`SCENARIO_COLLISION:${scenario}`);
  fs.mkdirSync(path.dirname(scenarioRoot), { recursive: true });
  fs.cpSync(sourceCase, scenarioRoot, { recursive: true, errorOnExist: true });
  const inspected = inspectCase(scenarioRoot, label);
  const spoolRoot = path.join(scenarioRoot, 'spool');
  const { VisionQueue } = require('../supervisor/vision_queue');
  let spawnCalls = 0;
  const queue = new VisionQueue({
    spoolRoot,
    workerScript: 'R05_A3_BLOCKED_WORKER_CLI',
    workerRoot: evidenceRoot,
    spawnWorker: () => {
      spawnCalls += 1;
      return fakeChild();
    },
  });
  const status = queue.create(inspected.request);
  assert.strictEqual(spawnCalls, 1);
  const jobDir = path.join(spoolRoot, 'jobs', status.job_id);
  const manifest = JSON.parse(fs.readFileSync(path.join(jobDir, 'manifest.json'), 'utf8'));
  return { ...inspected, jobDir, manifest, status, spawnCalls };
}

async function createSyntheticPage(context, label, networkAttempts) {
  const page = await context.newPage();
  assert.strictEqual(page.url(), 'about:blank');
  page.on('request', (request) => {
    if (/^(https?|wss?):/i.test(request.url())) {
      networkAttempts.push({ url: request.url(), resource_type: request.resourceType() });
    }
  });
  await page.setContent(`<!doctype html>
    <html><head><meta charset="utf-8"><title>R05 A3 ${label}</title></head>
    <body style="font-family:sans-serif;background:#111;color:#eee;padding:32px">
      <h1>SYNTHETIC LOCAL FILE INPUT TEST</h1>
      <p id="case-label"></p>
      <label for="synthetic-file-input">Synthetic approved image</label>
      <input id="synthetic-file-input" type="file" multiple>
      <pre id="result">NO FILE SELECTED</pre>
      <script>
        window.r05Events = { input: 0, change: 0 };
        const input = document.querySelector('#synthetic-file-input');
        input.addEventListener('input', () => { window.r05Events.input += 1; });
        input.addEventListener('change', () => { window.r05Events.change += 1; });
        document.querySelector('#case-label').textContent = ${JSON.stringify(label)};
      </script>
    </body></html>`);
  assert.strictEqual(page.url(), 'about:blank');
  return page;
}

function instrumentLocator(locator) {
  const calls = [];
  return {
    calls,
    target: {
      async setInputFiles(values, options) {
        calls.push(values.map((value) => ({
          name: value.name,
          mimeType: value.mimeType,
          size: value.buffer.length,
          sha256: sha256(value.buffer),
        })));
        return locator.setInputFiles(values, options);
      },
    },
  };
}

async function readDomFiles(page) {
  const values = await page.locator('#synthetic-file-input').evaluate(async (input) => {
    const files = [];
    for (const file of Array.from(input.files || [])) {
      files.push({
        name: file.name,
        type: file.type,
        size: file.size,
        bytes: Array.from(new Uint8Array(await file.arrayBuffer())),
      });
    }
    return { files, events: { ...window.r05Events } };
  });
  return {
    events: values.events,
    files: values.files.map((file) => {
      const buffer = Buffer.from(file.bytes);
      return {
        name: file.name,
        type: file.type,
        size: file.size,
        sha256: sha256(buffer),
      };
    }),
  };
}

function assertDomMatchesVerified(dom, verified) {
  assert.strictEqual(dom.files.length, verified.length);
  for (let index = 0; index < verified.length; index += 1) {
    assert.deepStrictEqual(dom.files[index], {
      name: verified[index].name,
      type: verified[index].mimeType,
      size: verified[index].buffer.length,
      sha256: verified[index].sha256,
    });
  }
}

async function positiveCase(context, chainRoot, evidenceRoot, label, scenario, networkAttempts, screenshotPath) {
  const { loadVerifiedInputs, uploadVerifiedInputs, markUploadConfirmed } = require('./vision-job');
  const prepared = prepareScenario(chainRoot, evidenceRoot, label, scenario);
  const page = await createSyntheticPage(context, scenario, networkAttempts);
  try {
    const verified = loadVerifiedInputs(prepared.jobDir, prepared.manifest);
    const instrumented = instrumentLocator(page.locator('#synthetic-file-input'));
    const handoff = await uploadVerifiedInputs(
      prepared.jobDir,
      prepared.manifest,
      instrumented.target,
      verified,
      { temporaryChatVerified: true },
    );
    const dom = await readDomFiles(page);
    assertDomMatchesVerified(dom, verified);
    assert.deepStrictEqual(dom.events, { input: 1, change: 1 });
    assert.strictEqual(instrumented.calls.length, 1);
    if (label === 'locally-redacted') {
      assert.ok(dom.files.every((file) => file.sha256 !== EXPECTED_CASES[label].forbiddenOriginalSha256));
    }
    await page.locator('#result').evaluate((node, value) => { node.textContent = value; },
      `LOCAL DOM SHA-256: ${dom.files.map((file) => file.sha256).join(', ')}`);
    if (screenshotPath) await page.screenshot({ path: screenshotPath, fullPage: true });
    const confirmed = markUploadConfirmed(prepared.jobDir, prepared.manifest, verified, handoff);
    assert.strictEqual(confirmed.state, 'upload_confirmed');
    return {
      label,
      scenario,
      job_id: prepared.status.job_id,
      approval_kind: prepared.approval.approval_kind,
      temporary_chat_verified_input: 'SYNTHETIC_TEST_FLAG_ONLY',
      confirmation_scope: 'LOCAL_TEST_ONLY',
      locator_set_input_files_calls: instrumented.calls.length,
      dom_events: dom.events,
      dom_files: dom.files,
      verified_sha256: verified.map((item) => item.sha256),
      page_url: page.url(),
      _page: page,
      _verified: verified,
      _prepared: prepared,
      _instrumented: instrumented,
    };
  } catch (error) {
    await page.close().catch(() => {});
    throw error;
  }
}

async function main() {
  if (!process.argv.includes(OPT_IN)) {
    process.stdout.write(`${JSON.stringify({
      status: 'NOT_RUN',
      reason: `explicit ${OPT_IN} required`,
      browser_launches: 0,
      public_navigation: 0,
      external_uploads: 0,
    })}\n`);
    return;
  }

  const chainRoot = argument('--chain-root');
  const evidenceRoot = argument('--evidence-root');
  const browserExecutable = argument('--browser-executable');
  const allowedEvidencePrefix = path.resolve('C:\\ai-lab-core-staging\\recovery\\R05_A3_LOCAL_BROWSER_');
  if (!evidenceRoot.toLowerCase().startsWith(allowedEvidencePrefix.toLowerCase())) {
    throw new Error('EVIDENCE_ROOT_NOT_R05_A3');
  }
  if (!fs.existsSync(chainRoot) || !fs.existsSync(evidenceRoot) || !fs.existsSync(browserExecutable)) {
    throw new Error('REQUIRED_PATH_MISSING');
  }
  process.env.NEXT_STABIL_VISION_WORKER_ROOT = evidenceRoot;

  const { chromium } = require('playwright');
  const playwrightPackage = require('playwright/package.json');
  const {
    loadVerifiedInputs,
    uploadVerifiedInputs,
    markUploadConfirmed,
    setCancelPath,
  } = require('./vision-job');
  setCancelPath(null);

  const startedAt = new Date().toISOString();
  const networkAttempts = [];
  const executableBytes = fs.readFileSync(browserExecutable);
  let browser;
  let context;
  try {
    browser = await chromium.launch({
      executablePath: browserExecutable,
      headless: true,
      args: [
        '--no-first-run',
        '--disable-background-networking',
        '--disable-component-update',
        '--disable-default-apps',
        '--disable-sync',
        '--metrics-recording-only',
      ],
    });
    context = await browser.newContext({
      acceptDownloads: false,
      offline: true,
      serviceWorkers: 'block',
    });
    await context.route(/^(https?|wss?):\/\//i, (route) => route.abort('blockedbyclient'));

    const publicSafe = await positiveCase(
      context, chainRoot, evidenceRoot, 'public-safe', 'A-public-safe', networkAttempts,
      path.join(evidenceRoot, 'synthetic-public-safe-filelist.png'),
    );
    const retryBefore = await readDomFiles(publicSafe._page);
    const retryCallsBefore = publicSafe._instrumented.calls.length;
    await assert.rejects(
      uploadVerifiedInputs(
        publicSafe._prepared.jobDir,
        publicSafe._prepared.manifest,
        publicSafe._instrumented.target,
        publicSafe._verified,
        { temporaryChatVerified: true },
      ),
      /UPLOAD_HANDOFF_ALREADY_EXISTS/,
    );
    const retryAfter = await readDomFiles(publicSafe._page);
    assert.deepStrictEqual(retryAfter, retryBefore);
    assert.strictEqual(publicSafe._instrumented.calls.length, retryCallsBefore);
    await publicSafe._page.close();

    const locallyRedacted = await positiveCase(
      context, chainRoot, evidenceRoot, 'locally-redacted', 'B-locally-redacted', networkAttempts,
    );
    await locallyRedacted._page.close();

    const tampered = prepareScenario(chainRoot, evidenceRoot, 'public-safe', 'C-tamper-after-read');
    const tamperPage = await createSyntheticPage(context, 'C-tamper-after-read', networkAttempts);
    const tamperVerified = loadVerifiedInputs(tampered.jobDir, tampered.manifest);
    const tamperOriginalHash = tamperVerified[0].sha256;
    fs.writeFileSync(path.join(tampered.jobDir, tampered.manifest.sources[0].relative_input_path),
      Buffer.from('R05-A3-SYNTHETIC-REPLACEMENT-AFTER-READ'));
    const tamperDiskHash = sha256(fs.readFileSync(
      path.join(tampered.jobDir, tampered.manifest.sources[0].relative_input_path),
    ));
    assert.notStrictEqual(tamperDiskHash, tamperOriginalHash);
    const tamperInstrumented = instrumentLocator(tamperPage.locator('#synthetic-file-input'));
    const tamperHandoff = await uploadVerifiedInputs(
      tampered.jobDir, tampered.manifest, tamperInstrumented.target, tamperVerified,
      { temporaryChatVerified: true },
    );
    const tamperDom = await readDomFiles(tamperPage);
    assertDomMatchesVerified(tamperDom, tamperVerified);
    assert.deepStrictEqual(tamperDom.events, { input: 1, change: 1 });
    assert.strictEqual(tamperInstrumented.calls.length, 1);
    markUploadConfirmed(tampered.jobDir, tampered.manifest, tamperVerified, tamperHandoff);
    await tamperPage.close();

    const badHash = prepareScenario(chainRoot, evidenceRoot, 'public-safe', 'E1-bad-hash-before-read');
    const badHashPage = await createSyntheticPage(context, 'E1-bad-hash-before-read', networkAttempts);
    fs.writeFileSync(path.join(badHash.jobDir, badHash.manifest.sources[0].relative_input_path),
      Buffer.from('R05-A3-SYNTHETIC-BAD-HASH'));
    assert.throws(() => loadVerifiedInputs(badHash.jobDir, badHash.manifest), /INPUT_CHECKSUM/);
    const badHashDom = await readDomFiles(badHashPage);
    assert.deepStrictEqual(badHashDom, { events: { input: 0, change: 0 }, files: [] });
    await badHashPage.close();

    const noTemporary = prepareScenario(chainRoot, evidenceRoot, 'public-safe', 'E2-temporary-flag-absent');
    const noTemporaryPage = await createSyntheticPage(context, 'E2-temporary-flag-absent', networkAttempts);
    const noTemporaryVerified = loadVerifiedInputs(noTemporary.jobDir, noTemporary.manifest);
    const noTemporaryInstrumented = instrumentLocator(noTemporaryPage.locator('#synthetic-file-input'));
    await assert.rejects(
      uploadVerifiedInputs(
        noTemporary.jobDir, noTemporary.manifest,
        noTemporaryInstrumented.target, noTemporaryVerified,
      ),
      /TEMPORARY_CHAT_NOT_VERIFIED/,
    );
    const noTemporaryDom = await readDomFiles(noTemporaryPage);
    assert.deepStrictEqual(noTemporaryDom, { events: { input: 0, change: 0 }, files: [] });
    assert.strictEqual(noTemporaryInstrumented.calls.length, 0);
    await noTemporaryPage.close();

    assert.deepStrictEqual(networkAttempts, []);
    const cleanResult = (value) => {
      const result = { ...value };
      for (const key of Object.keys(result)) if (key.startsWith('_')) delete result[key];
      return result;
    };
    const result = {
      status: 'REAL_BROWSER_FILELIST_EXACT_BYTES_PASS',
      started_at_utc: startedAt,
      finished_at_utc: new Date().toISOString(),
      code_under_test: 'd1b0518ad9aefb5bc05cd89308de923ca54d2809',
      process: {
        node: process.version,
        playwright: playwrightPackage.version,
        browser_version: browser.version(),
        browser_executable: browserExecutable,
        browser_executable_sha256: sha256(executableBytes),
        launch: 'chromium.launch / nonpersistent / headless',
      },
      isolation: {
        initial_page: 'about:blank',
        content_source: 'page.setContent in memory',
        context_offline: true,
        service_workers: 'block',
        unexpected_page_network_attempts: networkAttempts,
        public_navigation: 0,
        external_uploads: 0,
        normal_worker_run_calls: 0,
      },
      matrix: {
        A_public_safe: cleanResult(publicSafe),
        B_locally_redacted: cleanResult(locallyRedacted),
        C_tamper_after_read: {
          original_verified_sha256: tamperOriginalHash,
          replaced_disk_sha256: tamperDiskHash,
          dom_files: tamperDom.files,
          dom_events: tamperDom.events,
          locator_set_input_files_calls: tamperInstrumented.calls.length,
        },
        D_same_job_retry: {
          rejection: 'UPLOAD_HANDOFF_ALREADY_EXISTS',
          additional_locator_calls: 0,
          additional_input_events: 0,
          additional_change_events: 0,
          file_list_unchanged: true,
        },
        E_denials: {
          bad_hash: 'INPUT_CHECKSUM',
          temporary_chat_verified_absent: 'TEMPORARY_CHAT_NOT_VERIFIED',
          successful_file_selections: 0,
          dom_files_after_each: 0,
        },
      },
      limitations: [
        'temporaryChatVerified=true was a synthetic authorized input, not an observation of Temporary Chat',
        'page/request interception covers the isolated Playwright context, not whole-host traffic',
        'no ChatGPT page, remote uploader, external network, model, Supervisor, or production runtime was exercised',
      ],
    };
    const resultPath = path.join(evidenceRoot, 'browser-filepayload-result.json');
    fs.writeFileSync(resultPath, `${JSON.stringify(result, null, 2)}\n`, 'utf8');
    process.stdout.write(`${JSON.stringify(result)}\n`);
  } finally {
    setCancelPath(null);
    if (context) await context.close().catch(() => {});
    if (browser) await browser.close().catch(() => {});
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
