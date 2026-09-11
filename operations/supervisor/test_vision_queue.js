'use strict';

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { EventEmitter } = require('events');
const { VisionQueue } = require('./vision_queue');

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'vision-queue-'));
const requestKey = 'a'.repeat(64);
const incoming = path.join(root, 'incoming', requestKey);
fs.mkdirSync(incoming, { recursive: true });
const input = path.join(incoming, 'S1.png');
fs.writeFileSync(input, 'synthetic');
const sha256 = crypto.createHash('sha256').update('synthetic').digest('hex');
const children = [];
const queue = new VisionQueue({ spoolRoot: root, workerScript: 'worker.js', workerRoot: root, spawnWorker: () => {
  const child = new EventEmitter(); child.kill = () => child.emit('close', 2, 'cancelled'); children.push(child); return child;
} });
const request = { request_key: requestKey, sources: [{ source_ref: 'S1', document_id: 1, page_number: null, asset_id: null, sha256, incoming_relative_path: `incoming/${requestKey}/S1.png` }] };
const created = queue.create(request);
assert.strictEqual(queue.create(request).job_id, created.job_id);
assert.strictEqual(queue.health().status, 'BUSY');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'jobs', created.job_id, 'manifest.json'), 'utf8'));
assert.strictEqual(manifest.job_id, created.job_id);
assert.strictEqual(manifest.sources[0].sha256, sha256);
assert.deepStrictEqual(fs.readFileSync(path.join(root, 'jobs', created.job_id, 'input', 'S1.png')), Buffer.from('synthetic'));
fs.writeFileSync(path.join(root, 'jobs', created.job_id, 'upload_handoff.json'), `${JSON.stringify({
  schema_version: 'NEXT_STABIL_VISION_UPLOAD_HANDOFF_V1',
  job_id: created.job_id,
  state: 'upload_confirmed',
})}\n`, 'utf8');
children[0].visionOutput = 'TEMPORARY_CHAT_VERIFIED\nUPLOAD_COMPLETE\n';
children[0].emit('close', 0);
setImmediate(() => {
  assert.strictEqual(queue.get(created.job_id).state, 'COMPLETE');
  assert.strictEqual(queue.get('unknown'), null);
  queue._set(created.job_id, { state: 'QUEUED', next_retry_at: new Date().toISOString() });
  const cancelled = queue.cancel(created.job_id);
  assert.strictEqual(cancelled.state, 'CANCELLED');

  queue._set(created.job_id, {
    state: 'UI_CHANGED',
    attempt_count: 2,
    error_code: 'UI_CHANGED',
  });
  const retryablePause = new VisionQueue({
    spoolRoot: root,
    workerScript: 'unused',
    workerRoot: 'unused',
    spawnWorker: () => new EventEmitter(),
  });
  assert.strictEqual(retryablePause.health().status, 'UI_CHANGED');

  // An exhausted historical pause must not re-pause all jobs after restart.
  queue._set(created.job_id, {
    state: 'UI_CHANGED',
    attempt_count: 3,
    error_code: 'UI_CHANGED',
  });
  const recovered = new VisionQueue({
    spoolRoot: root,
    workerScript: 'unused',
    workerRoot: 'unused',
    spawnWorker: () => new EventEmitter(),
  });
  assert.strictEqual(recovered.health().status, 'READY');
  assert.strictEqual(cancelled.next_retry_at, null);
  assert.throws(() => queue.create({ request_key: 'b'.repeat(64), sources: [{ ...request.sources[0], incoming_relative_path: '../outside.png' }] }), /PATH/);
  assert.throws(() => queue.create({ ...request, request_key: 'c'.repeat(64), command: 'whoami' }), /FIELD/);
  assert.throws(() => queue.create({ ...request, request_key: 'd'.repeat(64), url: 'https://example.invalid/x.png' }), /FIELD/);
  assert.throws(() => queue.create({ request_key: 'e'.repeat(64), sources: [{ ...request.sources[0], url: 'https://example.invalid/x.png' }] }), /FIELD/);
  const badHashKey = '1'.repeat(64);
  const badHashIncoming = path.join(root, 'incoming', badHashKey);
  fs.mkdirSync(badHashIncoming, { recursive: true });
  fs.writeFileSync(path.join(badHashIncoming, 'S1.png'), 'tampered-incoming');
  assert.throws(() => queue.create({
    request_key: badHashKey,
    sources: [{
      ...request.sources[0],
      sha256,
      incoming_relative_path: `incoming/${badHashKey}/S1.png`,
    }],
  }), /SOURCE_CHECKSUM/);

  const uncertainRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'vision-queue-uncertain-'));
  const uncertainIncoming = path.join(uncertainRoot, 'incoming', 'f'.repeat(64));
  fs.mkdirSync(uncertainIncoming, { recursive: true });
  fs.writeFileSync(path.join(uncertainIncoming, 'S1.png'), 'uncertain');
  const uncertainChildren = [];
  const uncertainQueue = new VisionQueue({
    spoolRoot: uncertainRoot,
    workerScript: 'unused',
    workerRoot: 'unused',
    spawnWorker: () => {
      const child = new EventEmitter();
      uncertainChildren.push(child);
      return child;
    },
  });
  const uncertain = uncertainQueue.create({
    request_key: 'f'.repeat(64),
    sources: [{
      source_ref: 'S1', document_id: 2, page_number: null, asset_id: null,
      sha256: crypto.createHash('sha256').update('uncertain').digest('hex'),
      incoming_relative_path: `incoming/${'f'.repeat(64)}/S1.png`,
    }],
  });
  fs.writeFileSync(path.join(uncertainRoot, 'jobs', uncertain.job_id, 'upload_handoff.json'), `${JSON.stringify({
    schema_version: 'NEXT_STABIL_VISION_UPLOAD_HANDOFF_V1',
    job_id: uncertain.job_id,
    state: 'contact_may_have_started',
  })}\n`, 'utf8');
  uncertainChildren[0].visionOutput = 'WORKER_ERROR_CODE=SYNTHETIC_CRASH\n';
  uncertainChildren[0].emit('close', 1);
  assert.strictEqual(uncertainQueue.get(uncertain.job_id).state, 'UPLOAD_UNCERTAIN');
  assert.strictEqual(uncertainQueue.get(uncertain.job_id).next_retry_at, null);
  assert.strictEqual(uncertainQueue.health().queued, 0);
  const recoveredUncertain = new VisionQueue({
    spoolRoot: uncertainRoot,
    workerScript: 'unused',
    workerRoot: 'unused',
    spawnWorker: () => { throw new Error('UNEXPECTED_SECOND_UPLOAD'); },
  });
  assert.strictEqual(recoveredUncertain.get(uncertain.job_id).state, 'UPLOAD_UNCERTAIN');
  assert.strictEqual(recoveredUncertain.health().queued, 0);
  uncertainQueue._set(uncertain.job_id, { state: 'QUEUED', attempt_count: 1 });
  uncertainQueue.queue.push(uncertain.job_id);
  uncertainQueue.pump();
  assert.strictEqual(uncertainQueue.get(uncertain.job_id).state, 'RUNNING');
  uncertainChildren[1].visionOutput = 'WORKER_STATUS=UI_CHANGED\n';
  uncertainChildren[1].emit('close', 21);
  assert.strictEqual(uncertainQueue.get(uncertain.job_id).state, 'UPLOAD_UNCERTAIN');
  assert.strictEqual(uncertainQueue.health().queued, 0);

  const missingMarkerRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'vision-queue-no-marker-'));
  const missingIncoming = path.join(missingMarkerRoot, 'incoming', '9'.repeat(64));
  fs.mkdirSync(missingIncoming, { recursive: true });
  fs.writeFileSync(path.join(missingIncoming, 'S1.png'), 'missing-marker');
  const missingMarkerChildren = [];
  const missingMarkerQueue = new VisionQueue({
    spoolRoot: missingMarkerRoot,
    workerScript: 'unused',
    workerRoot: 'unused',
    spawnWorker: () => {
      const child = new EventEmitter();
      missingMarkerChildren.push(child);
      return child;
    },
  });
  const missingMarker = missingMarkerQueue.create({
    request_key: '9'.repeat(64),
    sources: [{
      source_ref: 'S1', document_id: 3, page_number: null, asset_id: null,
      sha256: crypto.createHash('sha256').update('missing-marker').digest('hex'),
      incoming_relative_path: `incoming/${'9'.repeat(64)}/S1.png`,
    }],
  });
  missingMarkerChildren[0].visionOutput = 'UPLOAD_COMPLETE\n';
  missingMarkerChildren[0].emit('close', 0);
  assert.strictEqual(missingMarkerQueue.get(missingMarker.job_id).state, 'UPLOAD_UNCERTAIN');
  assert.strictEqual(missingMarkerQueue.get(missingMarker.job_id).error_code, 'UPLOAD_HANDOFF_EVIDENCE_MISSING');

  const copyRaceRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'vision-queue-copy-race-'));
  const copyRaceKey = '2'.repeat(64);
  const copyRaceIncoming = path.join(copyRaceRoot, 'incoming', copyRaceKey);
  const approvedCopyBytes = Buffer.from('approved-copy-bytes');
  fs.mkdirSync(copyRaceIncoming, { recursive: true });
  const copyRaceInput = path.join(copyRaceIncoming, 'S1.png');
  fs.writeFileSync(copyRaceInput, approvedCopyBytes);
  const copyRaceChildren = [];
  const originalWriteFileSync = fs.writeFileSync;
  let raceMutationApplied = false;
  fs.writeFileSync = function guardedWrite(filePath, value, options) {
    if (
      !raceMutationApplied
      && path.basename(String(filePath)) === 'S1.png'
      && String(filePath).includes(`${path.sep}jobs${path.sep}`)
    ) {
      originalWriteFileSync(copyRaceInput, Buffer.from('replacement-after-read'));
      raceMutationApplied = true;
    }
    return originalWriteFileSync(filePath, value, options);
  };
  let copyRaceQueue;
  let copyRace;
  try {
    copyRaceQueue = new VisionQueue({
      spoolRoot: copyRaceRoot,
      workerScript: 'unused',
      workerRoot: 'unused',
      spawnWorker: () => {
        const child = new EventEmitter();
        copyRaceChildren.push(child);
        return child;
      },
    });
    copyRace = copyRaceQueue.create({
      request_key: copyRaceKey,
      sources: [{
        source_ref: 'S1', document_id: 4, page_number: null, asset_id: null,
        sha256: crypto.createHash('sha256').update(approvedCopyBytes).digest('hex'),
        incoming_relative_path: `incoming/${copyRaceKey}/S1.png`,
      }],
    });
  } finally {
    fs.writeFileSync = originalWriteFileSync;
  }
  assert.strictEqual(raceMutationApplied, true);
  assert.deepStrictEqual(
    fs.readFileSync(path.join(copyRaceRoot, 'jobs', copyRace.job_id, 'input', 'S1.png')),
    approvedCopyBytes,
  );
  copyRaceChildren[0].visionOutput = 'UPLOAD_COMPLETE\n';
  copyRaceChildren[0].emit('close', 0);
  assert.strictEqual(copyRaceQueue.get(copyRace.job_id).state, 'UPLOAD_UNCERTAIN');

  fs.rmSync(root, { recursive: true, force: true });
  fs.rmSync(uncertainRoot, { recursive: true, force: true });
  fs.rmSync(missingMarkerRoot, { recursive: true, force: true });
  fs.rmSync(copyRaceRoot, { recursive: true, force: true });
  process.stdout.write('VISION SUPERVISOR QUEUE TESTS: OK\n');
});
