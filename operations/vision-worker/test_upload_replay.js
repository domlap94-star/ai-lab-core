'use strict';

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { EventEmitter } = require('events');
const { VisionQueue } = require('../supervisor/vision_queue');
const {
  loadVerifiedInputs,
  uploadVerifiedInputs,
  setCancelPath,
} = require('./vision-job');

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function tick() {
  return new Promise((resolve) => setImmediate(resolve));
}

function writeRecoveredJob(spoolRoot, jobId, bytes) {
  const jobDir = path.join(spoolRoot, 'jobs', jobId);
  fs.mkdirSync(path.join(jobDir, 'input'), { recursive: true });
  fs.mkdirSync(path.join(jobDir, 'output'), { recursive: true });
  fs.mkdirSync(path.join(spoolRoot, 'incoming'), { recursive: true });
  fs.writeFileSync(path.join(jobDir, 'input', 'S1.png'), bytes);
  const manifest = {
    schema_version: 'NEXT_STABIL_VISION_JOB_V1',
    job_id: jobId,
    analysis_goal: 'technical_visual_analysis',
    sources: [{
      source_ref: 'S1',
      document_id: 910001,
      page_number: null,
      asset_id: null,
      sha256: sha256(bytes),
      relative_input_path: 'input/S1.png',
    }],
  };
  fs.writeFileSync(path.join(jobDir, 'manifest.json'), `${JSON.stringify(manifest)}\n`, 'utf8');
  fs.writeFileSync(path.join(jobDir, 'status.json'), `${JSON.stringify({
    job_id: jobId,
    request_key: 'a'.repeat(64),
    state: 'RUNNING',
    attempt_count: 1,
    error_code: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    next_retry_at: null,
  })}\n`, 'utf8');
  return { jobDir, manifest };
}

function fakeFileInput(received) {
  return {
    async setInputFiles(values) {
      received.push(...values.map((value) => Buffer.from(value.buffer)));
    },
  };
}

class DeferredArbiter {
  constructor() {
    this.callback = null;
    this.owner = null;
  }

  acquire(kind, jobId, callback) {
    this.owner = { kind, jobId };
    this.callback = callback;
    return true;
  }

  release() {
    this.owner = null;
    return true;
  }

  pause() {}
  resume() {}
  cancel() {}
  health() { return { owner_type: this.owner?.kind || null }; }
}

async function recoverRace() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'vision-upload-recover-race-'));
  try {
    const jobId = '91919191-9191-9191-9191-919191919191';
    const { jobDir, manifest } = writeRecoveredJob(root, jobId, Buffer.from('recover-race-approved'));
    const arbiter = new DeferredArbiter();
    const spawned = [];
    const queue = new VisionQueue({
      spoolRoot: root,
      workerScript: 'blocked-worker-cli',
      workerRoot: 'blocked-worker-root',
      arbiter,
      spawnWorker: () => {
        const child = new EventEmitter();
        child.kill = () => {};
        spawned.push(child);
        return child;
      },
    });
    await tick();
    assert.strictEqual(typeof arbiter.callback, 'function');

    const verified = loadVerifiedInputs(jobDir, manifest);
    const received = [];
    await uploadVerifiedInputs(jobDir, manifest, fakeFileInput(received), verified, {
      temporaryChatVerified: true,
    });
    assert.strictEqual(received.length, 1);

    arbiter.callback();
    if (spawned.length > 0) {
      await uploadVerifiedInputs(jobDir, manifest, fakeFileInput(received), verified, {
        temporaryChatVerified: true,
      });
    }
    return {
      restarted_spawns: spawned.length,
      fake_uploads: received.length,
      final_state: queue.get(jobId).state,
    };
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

async function parallelBoundary() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'vision-upload-parallel-'));
  try {
    const jobId = '92929292-9292-9292-9292-929292929292';
    const { jobDir, manifest } = writeRecoveredJob(root, jobId, Buffer.from('parallel-approved'));
    const verified = loadVerifiedInputs(jobDir, manifest);
    const received = [];
    let releaseUpload;
    const gate = new Promise((resolve) => { releaseUpload = resolve; });
    const fileInput = {
      async setInputFiles(values) {
        received.push(...values.map((value) => Buffer.from(value.buffer)));
        await gate;
      },
    };
    const first = uploadVerifiedInputs(jobDir, manifest, fileInput, verified, {
      temporaryChatVerified: true,
    });
    const second = uploadVerifiedInputs(jobDir, manifest, fileInput, verified, {
      temporaryChatVerified: true,
    });
    const settledPromise = Promise.allSettled([first, second]);
    await tick();
    releaseUpload();
    const settled = await settledPromise;
    return {
      fulfilled: settled.filter((item) => item.status === 'fulfilled').length,
      rejected: settled.filter((item) => item.status === 'rejected').length,
      rejection_codes: settled
        .filter((item) => item.status === 'rejected')
        .map((item) => String(item.reason?.message || item.reason)),
      fake_uploads: received.length,
    };
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

async function main() {
  const vulnerableMode = process.argv.includes('--expect-vulnerable');
  const recover = await recoverRace();
  const parallel = await parallelBoundary();
  if (vulnerableMode) {
    assert.strictEqual(recover.restarted_spawns, 1);
    assert.strictEqual(recover.fake_uploads, 2);
    assert.strictEqual(parallel.fulfilled, 2);
    assert.strictEqual(parallel.fake_uploads, 2);
  } else {
    assert.strictEqual(recover.restarted_spawns, 0);
    assert.strictEqual(recover.fake_uploads, 1);
    assert.strictEqual(recover.final_state, 'UPLOAD_UNCERTAIN');
    assert.strictEqual(parallel.fulfilled, 1);
    assert.strictEqual(parallel.rejected, 1);
    assert.deepStrictEqual(parallel.rejection_codes, ['UPLOAD_HANDOFF_ALREADY_EXISTS']);
    assert.strictEqual(parallel.fake_uploads, 1);
  }
  process.stdout.write(`${JSON.stringify({
    status: vulnerableMode ? 'R05_A2_UPLOAD_REPLAY_REPRODUCED' : 'R05_A2_UPLOAD_REPLAY_GUARD_OK',
    recover,
    parallel,
    browser_launches: 0,
    network_calls: 0,
  })}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
}).finally(() => setCancelPath(null));
