'use strict';

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { EventEmitter } = require('events');
const { VisionQueue } = require('../supervisor/vision_queue');
const {
  run,
  setCancelPath,
  loadVerifiedInputs,
  uploadVerifiedInputs,
  markUploadConfirmed,
  UPLOAD_HANDOFF_FILE,
  UPLOAD_HANDOFF_SCHEMA,
} = require('./vision-job');

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function manifestFor(jobId, sources) {
  return {
    schema_version: 'NEXT_STABIL_VISION_JOB_V1',
    job_id: jobId,
    analysis_goal: 'technical_visual_analysis',
    sources,
  };
}

function createJob(root, jobId, bytes, extension = '.png') {
  const jobDir = path.join(root, jobId);
  fs.mkdirSync(path.join(jobDir, 'input'), { recursive: true });
  fs.mkdirSync(path.join(jobDir, 'output'), { recursive: true });
  const input = path.join(jobDir, 'input', `S1${extension}`);
  fs.writeFileSync(input, bytes);
  const manifest = manifestFor(jobId, [{
    source_ref: 'S1',
    document_id: 900001,
    page_number: null,
    asset_id: null,
    sha256: sha256(bytes),
    relative_input_path: `input/S1${extension}`,
  }]);
  fs.writeFileSync(path.join(jobDir, 'manifest.json'), `${JSON.stringify(manifest)}\n`, 'utf8');
  return { jobDir, input, manifest };
}

function fakeFileInput(received) {
  return {
    async setInputFiles(values) {
      received.push(...values.map((value) => ({
        name: value.name,
        mimeType: value.mimeType,
        buffer: Buffer.from(value.buffer),
      })));
    },
  };
}

function locator(visible = false) {
  return {
    first() { return this; },
    async isVisible() { return visible; },
    async waitFor() {},
    async count() { return visible ? 1 : 0; },
    async getAttribute() { return null; },
    async click() {},
    async fill() {},
    async press() {},
  };
}

function chromiumStoppingAt(mode) {
  let uploadCalls = 0;
  const page = {
    url() { return 'https://chatgpt.com/'; },
    locator() { return locator(false); },
    getByRole(role, options = {}) {
      const name = String(options.name || '');
      if ((role === 'button' || role === 'link') && /Log in/.test(name)) {
        return locator(mode === 'AUTH_REQUIRED');
      }
      if (role === 'textbox') return locator(true);
      return locator(false);
    },
    async goto() {},
    async newPage() { return page; },
    async close() {},
  };
  const chromium = {
    async launchPersistentContext() {
      return {
        pages() { return [page]; },
        async newPage() { return page; },
        async close() {},
      };
    },
  };
  return { chromium, uploadCalls: () => uploadCalls };
}

function fakeChild(children) {
  const child = new EventEmitter();
  child.kill = () => {};
  children.push(child);
  return child;
}

async function processBackendCase(caseRoot) {
  const request = JSON.parse(fs.readFileSync(path.join(caseRoot, 'request.json'), 'utf8'));
  const approval = JSON.parse(fs.readFileSync(path.join(caseRoot, 'approval.json'), 'utf8'));
  const spoolRoot = path.join(caseRoot, 'spool');
  const children = [];
  const queue = new VisionQueue({
    spoolRoot,
    workerScript: 'blocked-worker-cli',
    workerRoot: 'blocked-worker-root',
    spawnWorker: () => fakeChild(children),
  });
  const status = queue.create(request);
  assert.strictEqual(children.length, 1);
  const jobDir = path.join(spoolRoot, 'jobs', status.job_id);
  const manifest = JSON.parse(fs.readFileSync(path.join(jobDir, 'manifest.json'), 'utf8'));
  const verified = loadVerifiedInputs(jobDir, manifest);
  const received = [];
  const handoff = await uploadVerifiedInputs(jobDir, manifest, fakeFileInput(received), verified, {
    temporaryChatVerified: true,
  });
  assert.strictEqual(received.length, request.sources.length);
  for (const value of received) {
    assert.deepStrictEqual(Object.keys(value).sort(), ['buffer', 'mimeType', 'name']);
    assert.strictEqual(sha256(value.buffer), approval.final_sha256[value.name.slice(0, 2)]);
  }
  if (approval.forbidden_original_sha256) {
    assert.ok(received.every((value) => sha256(value.buffer) !== approval.forbidden_original_sha256));
  }
  markUploadConfirmed(jobDir, manifest, verified, handoff);
  const marker = JSON.parse(fs.readFileSync(path.join(jobDir, UPLOAD_HANDOFF_FILE), 'utf8'));
  assert.strictEqual(marker.schema_version, UPLOAD_HANDOFF_SCHEMA);
  assert.strictEqual(marker.state, 'upload_confirmed');
  assert.deepStrictEqual(marker.sources.map((source) => source.sha256), request.sources.map((source) => source.sha256));
  children[0].visionOutput = 'TEMPORARY_CHAT_VERIFIED\nUPLOAD_COMPLETE\n';
  children[0].emit('close', 0);
  assert.strictEqual(queue.get(status.job_id).state, 'COMPLETE');
  return {
    label: approval.label,
    job_id: status.job_id,
    request_key: request.request_key,
    received_sha256: received.map((value) => sha256(value.buffer)),
  };
}

async function main() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'vision-upload-boundary-'));
  try {
    const approvedBytes = Buffer.from('synthetic-approved-bytes');
    const job = createJob(root, '11111111-1111-1111-1111-111111111111', approvedBytes);
    const verified = loadVerifiedInputs(job.jobDir, job.manifest);
    fs.writeFileSync(job.input, 'synthetic-replacement-bytes');
    const received = [];
    const firstHandoff = await uploadVerifiedInputs(job.jobDir, job.manifest, fakeFileInput(received), verified, {
      temporaryChatVerified: true,
    });
    assert.strictEqual(received.length, 1);
    assert.strictEqual(sha256(received[0].buffer), sha256(approvedBytes));
    assert.notStrictEqual(sha256(received[0].buffer), sha256(fs.readFileSync(job.input)));
    assert.strictEqual(received[0].name, 'S1.png');
    assert.strictEqual(received[0].mimeType, 'image/png');
    assert.throws(
      () => markUploadConfirmed(job.jobDir, { ...job.manifest, job_id: '93939393-9393-9393-9393-939393939393' }, verified, firstHandoff),
      /UPLOAD_HANDOFF_OWNERSHIP/,
    );
    assert.throws(
      () => markUploadConfirmed(job.jobDir, job.manifest, [{
        ...verified[0],
        sha256: '0'.repeat(64),
      }], firstHandoff),
      /UPLOAD_HANDOFF_OWNERSHIP/,
    );
    assert.throws(
      () => markUploadConfirmed(job.jobDir, job.manifest, verified, {
        ...firstHandoff,
        attempt_id: crypto.randomUUID(),
      }),
      /UPLOAD_HANDOFF_OWNERSHIP/,
    );
    const confirmed = markUploadConfirmed(job.jobDir, job.manifest, verified, firstHandoff);
    assert.strictEqual(confirmed.state, 'upload_confirmed');
    const confirmedMarkerBytes = fs.readFileSync(path.join(job.jobDir, UPLOAD_HANDOFF_FILE));
    await assert.rejects(
      uploadVerifiedInputs(job.jobDir, job.manifest, fakeFileInput(received), verified, {
        temporaryChatVerified: true,
      }),
      /UPLOAD_HANDOFF_ALREADY_EXISTS/,
    );
    assert.strictEqual(received.length, 1);
    assert.deepStrictEqual(fs.readFileSync(path.join(job.jobDir, UPLOAD_HANDOFF_FILE)), confirmedMarkerBytes);

    const tampered = createJob(root, '22222222-2222-2222-2222-222222222222', Buffer.from('trusted'));
    fs.writeFileSync(tampered.input, 'changed');
    assert.throws(() => loadVerifiedInputs(tampered.jobDir, tampered.manifest), /INPUT_CHECKSUM/);

    const unsafe = createJob(root, '33333333-3333-3333-3333-333333333333', Buffer.from('safe'));
    const unsafeManifest = manifestFor(unsafe.manifest.job_id, [{
      ...unsafe.manifest.sources[0],
      relative_input_path: '../outside.png',
    }]);
    assert.throws(() => loadVerifiedInputs(unsafe.jobDir, unsafeManifest), /MANIFEST_INPUT_PATH/);

    const outside = path.join(root, 'outside');
    fs.mkdirSync(outside, { recursive: true });
    fs.writeFileSync(path.join(outside, 'S1.png'), 'outside-bytes');
    const linkedDir = path.join(root, '44444444-4444-4444-4444-444444444444');
    fs.mkdirSync(linkedDir, { recursive: true });
    fs.symlinkSync(outside, path.join(linkedDir, 'input'), process.platform === 'win32' ? 'junction' : 'dir');
    const linkedManifest = manifestFor(path.basename(linkedDir), [{
      source_ref: 'S1', document_id: 900004, page_number: null, asset_id: null,
      sha256: sha256(Buffer.from('outside-bytes')), relative_input_path: 'input/S1.png',
    }]);
    assert.throws(() => loadVerifiedInputs(linkedDir, linkedManifest), /INPUT_PATH/);

    const neighbour = createJob(root, '55555555-5555-5555-5555-555555555555', Buffer.from('neighbour'));
    const neighbourInputs = loadVerifiedInputs(neighbour.jobDir, neighbour.manifest);
    assert.notStrictEqual(neighbourInputs[0].sha256, verified[0].sha256);
    assert.strictEqual(neighbourInputs[0].source_ref, verified[0].source_ref);
    const neighbourReceived = [];
    const neighbourHandoff = await uploadVerifiedInputs(
      neighbour.jobDir,
      neighbour.manifest,
      fakeFileInput(neighbourReceived),
      neighbourInputs,
      { temporaryChatVerified: true },
    );
    assert.strictEqual(neighbourReceived.length, 1);
    assert.strictEqual(markUploadConfirmed(
      neighbour.jobDir,
      neighbour.manifest,
      neighbourInputs,
      neighbourHandoff,
    ).state, 'upload_confirmed');

    for (const markerCase of [
      { id: '56565656-5656-5656-5656-565656565656', value: '{' },
      {
        id: '57575757-5757-5757-5757-575757575757',
        value: `${JSON.stringify({
          schema_version: 'NEXT_STABIL_VISION_UPLOAD_HANDOFF_V1',
          job_id: '57575757-5757-5757-5757-575757575757',
          state: 'contact_may_have_started',
        })}\n`,
      },
    ]) {
      const marked = createJob(root, markerCase.id, Buffer.from(`marked-${markerCase.id}`));
      const markedInputs = loadVerifiedInputs(marked.jobDir, marked.manifest);
      const markerPath = path.join(marked.jobDir, UPLOAD_HANDOFF_FILE);
      fs.writeFileSync(markerPath, markerCase.value, 'utf8');
      const originalMarker = fs.readFileSync(markerPath);
      const markedReceived = [];
      await assert.rejects(
        uploadVerifiedInputs(marked.jobDir, marked.manifest, fakeFileInput(markedReceived), markedInputs, {
          temporaryChatVerified: true,
        }),
        /UPLOAD_HANDOFF_ALREADY_EXISTS/,
      );
      assert.strictEqual(markedReceived.length, 0);
      assert.deepStrictEqual(fs.readFileSync(markerPath), originalMarker);
    }

    const interrupted = createJob(root, '58585858-5858-5858-5858-585858585858', Buffer.from('interrupted'));
    const interruptedInputs = loadVerifiedInputs(interrupted.jobDir, interrupted.manifest);
    let interruptedCalls = 0;
    await assert.rejects(
      uploadVerifiedInputs(interrupted.jobDir, interrupted.manifest, {
        async setInputFiles() {
          interruptedCalls += 1;
          throw new Error('SYNTHETIC_CONTACT_INTERRUPTED');
        },
      }, interruptedInputs, { temporaryChatVerified: true }),
      /SYNTHETIC_CONTACT_INTERRUPTED/,
    );
    await assert.rejects(
      uploadVerifiedInputs(interrupted.jobDir, interrupted.manifest, fakeFileInput([]), interruptedInputs, {
        temporaryChatVerified: true,
      }),
      /UPLOAD_HANDOFF_ALREADY_EXISTS/,
    );
    assert.strictEqual(interruptedCalls, 1);
    assert.strictEqual(
      JSON.parse(fs.readFileSync(path.join(interrupted.jobDir, UPLOAD_HANDOFF_FILE), 'utf8')).state,
      'contact_may_have_started',
    );

    const cancelAfterClaim = createJob(root, '59595959-5959-5959-5959-595959595959', Buffer.from('cancel-after-claim'));
    const cancelAfterClaimInputs = loadVerifiedInputs(cancelAfterClaim.jobDir, cancelAfterClaim.manifest);
    const cancelAfterClaimPath = path.join(cancelAfterClaim.jobDir, 'cancel.requested');
    const cancelAfterClaimReceived = [];
    const originalFsyncSync = fs.fsyncSync;
    fs.fsyncSync = function cancelAtDurableClaim(descriptor) {
      originalFsyncSync(descriptor);
      fs.writeFileSync(cancelAfterClaimPath, '', 'utf8');
    };
    setCancelPath(cancelAfterClaimPath);
    try {
      await assert.rejects(
        uploadVerifiedInputs(
          cancelAfterClaim.jobDir,
          cancelAfterClaim.manifest,
          fakeFileInput(cancelAfterClaimReceived),
          cancelAfterClaimInputs,
          { temporaryChatVerified: true },
        ),
        /CANCELLED/,
      );
    } finally {
      fs.fsyncSync = originalFsyncSync;
      setCancelPath(null);
    }
    assert.strictEqual(cancelAfterClaimReceived.length, 0);
    assert.strictEqual(
      JSON.parse(fs.readFileSync(path.join(cancelAfterClaim.jobDir, UPLOAD_HANDOFF_FILE), 'utf8')).state,
      'contact_may_have_started',
    );

    const cancelled = createJob(root, '66666666-6666-6666-6666-666666666666', Buffer.from('cancelled'));
    const cancelledInputs = loadVerifiedInputs(cancelled.jobDir, cancelled.manifest);
    fs.writeFileSync(path.join(cancelled.jobDir, 'cancel.requested'), '', 'utf8');
    setCancelPath(path.join(cancelled.jobDir, 'cancel.requested'));
    const cancelledReceived = [];
    await assert.rejects(
      uploadVerifiedInputs(cancelled.jobDir, cancelled.manifest, fakeFileInput(cancelledReceived), cancelledInputs, { temporaryChatVerified: true }),
      /CANCELLED/,
    );
    assert.strictEqual(cancelledReceived.length, 0);
    setCancelPath(null);

    const unverifiedReceived = [];
    await assert.rejects(
      uploadVerifiedInputs(neighbour.jobDir, neighbour.manifest, fakeFileInput(unverifiedReceived), neighbourInputs),
      /TEMPORARY_CHAT_NOT_VERIFIED/,
    );
    assert.strictEqual(unverifiedReceived.length, 0);

    for (const expected of ['AUTH_REQUIRED', 'UI_CHANGED']) {
      const stopped = createJob(root, `${expected === 'AUTH_REQUIRED' ? '7' : '8'}`.repeat(8) + '-1111-1111-1111-111111111111', Buffer.from(expected));
      const fake = chromiumStoppingAt(expected);
      await assert.rejects(run(stopped.jobDir, { chromium: fake.chromium }), new RegExp(expected));
      assert.strictEqual(fake.uploadCalls(), 0);
      assert.strictEqual(fs.existsSync(path.join(stopped.jobDir, UPLOAD_HANDOFF_FILE)), false);
    }

    const chainIndex = process.argv.indexOf('--chain-root');
    let chainResults = [];
    if (chainIndex >= 0) {
      const chainRoot = path.resolve(process.argv[chainIndex + 1]);
      const cases = fs.readdirSync(chainRoot, { withFileTypes: true })
        .filter((entry) => entry.isDirectory())
        .map((entry) => path.join(chainRoot, entry.name))
        .sort();
      assert.strictEqual(cases.length, 2);
      const replayRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'vision-backend-chain-replay-'));
      try {
        for (const caseRoot of cases) {
          const replayCase = path.join(replayRoot, path.basename(caseRoot));
          fs.cpSync(caseRoot, replayCase, { recursive: true, errorOnExist: true });
          chainResults.push(await processBackendCase(replayCase));
        }
        assert.notStrictEqual(chainResults[0].request_key, chainResults[1].request_key);
        assert.notStrictEqual(chainResults[0].job_id, chainResults[1].job_id);
      } finally {
        fs.rmSync(replayRoot, { recursive: true, force: true });
      }
    }

    process.stdout.write(`${JSON.stringify({
      status: 'R05_A2_UPLOAD_BOUNDARY_TESTS_OK',
      local_cases: 17,
      backend_chain_cases: chainResults,
      browser_launches: 0,
      network_calls: 0,
    })}\n`);
  } finally {
    setCancelPath(null);
    fs.rmSync(root, { recursive: true, force: true });
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
