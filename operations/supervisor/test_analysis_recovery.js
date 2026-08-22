'use strict';

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { EventEmitter } = require('events');
const { AnalysisQueue } = require('./analysis_queue');

function fixture(root) {
  const value = {
    schema_version: 'NEXT_STABIL_ADVANCED_ANALYSIS_V1',
    analysis_id: crypto.randomUUID(),
    analysis_type: 'technical_interpretation',
    problem: 'Synthetic public fixture',
    sources: [{ source_ref: 'S1', source_sha256: 'c'.repeat(64), technical_excerpt: 'R = U / I', page: 1 }],
    tables: [], formulas: [], variables: {}, values: {}, units: {}, constraints: [], standards: [], claims: [],
    requested_output: 'result', validation_requirements: [],
  };
  const raw = JSON.stringify(value);
  const hash = crypto.createHash('sha256').update(raw).digest('hex');
  const incoming = path.join(root, 'incoming', hash);
  fs.mkdirSync(incoming, { recursive: true });
  fs.writeFileSync(path.join(incoming, 'package.json'), raw);
  return {
    request_key: crypto.randomBytes(32).toString('hex'),
    analysis_id: value.analysis_id,
    analysis_type: value.analysis_type,
    package_sha256: hash,
    incoming_relative_path: `incoming/${hash}/package.json`,
  };
}

function child(list) {
  const value = new EventEmitter();
  value.kill = () => {};
  list.push(value);
  return value;
}

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'analysis-recovery-'));
const children = [];
const queue = new AnalysisQueue({
  spoolRoot: root, workerScript: 'x', workerRoot: root,
  spawnWorker: () => child(children),
});
const request = fixture(root);
const created = queue.create(request);
assert.strictEqual(children.length, 1);
children[0].analysisOutput = 'AUTH_REQUIRED';
children[0].emit('close', 20);
assert.strictEqual(queue.get(created.job_id).state, 'AUTH_REQUIRED');
assert.strictEqual(queue.health().browser.paused_state, 'AUTH_REQUIRED');

const resumedChildren = [];
const recovered = new AnalysisQueue({
  spoolRoot: root, workerScript: 'x', workerRoot: root,
  spawnWorker: () => child(resumedChildren),
});
assert.strictEqual(recovered.health().status, 'AUTH_REQUIRED');
recovered.resume();
setImmediate(() => {
  assert.strictEqual(resumedChildren.length, 1);
  resumedChildren[0].analysisOutput = 'TEMPORARY_CHAT_VERIFIED';
  resumedChildren[0].emit('close', 0);
  setImmediate(() => {
    assert.strictEqual(recovered.get(created.job_id).state, 'COMPLETE');
    assert.throws(() => queue.create({ ...request, request_key: crypto.randomBytes(32).toString('hex'), incoming_relative_path: '../package.json' }), /INVALID/);
    const cancelled = recovered.create(fixture(root));
    assert.strictEqual(resumedChildren.length, 2);
    recovered.cancel(cancelled.job_id);
    resumedChildren[1].analysisOutput = 'WORKER_ERROR_CODE=CANCELLED';
    resumedChildren[1].emit('close', 22);
    assert.strictEqual(recovered.get(cancelled.job_id).state, 'CANCELLED');

    const runningRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'analysis-running-'));
    const abandoned = [];
    const first = new AnalysisQueue({
      spoolRoot: runningRoot, workerScript: 'x', workerRoot: runningRoot,
      spawnWorker: () => child(abandoned),
    });
    const running = first.create(fixture(runningRoot));
    assert.strictEqual(first.get(running.job_id).state, 'RUNNING');
    const restartedChildren = [];
    const restarted = new AnalysisQueue({
      spoolRoot: runningRoot, workerScript: 'x', workerRoot: runningRoot,
      spawnWorker: () => child(restartedChildren),
    });
    setImmediate(() => {
      assert.strictEqual(restartedChildren.length, 1);
      restartedChildren[0].analysisOutput = 'WORKER_ERROR_CODE=RESPONSE_TIMEOUT';
      restartedChildren[0].emit('close', 1);
      setImmediate(() => {
        assert.strictEqual(restarted.get(running.job_id).error_code, 'RESPONSE_TIMEOUT');
        fs.rmSync(root, { recursive: true, force: true });
        fs.rmSync(runningRoot, { recursive: true, force: true });
        process.stdout.write('ANALYSIS DURABLE RECOVERY + PAUSE: OK\n');
      });
    });
  });
});
