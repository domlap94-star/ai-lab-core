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
    analysis_id: crypto.randomUUID(), analysis_type: 'formula_calculation',
    problem: 'Synthetic public fixture',
    sources: [{ source_ref: 'S1', source_sha256: 'd'.repeat(64), technical_excerpt: 'P = F / A', page: 1 }],
    tables: [], formulas: ['force/area'], variables: { force: 12, area: 0.4 },
    values: { force: 12, area: 0.4 }, units: { force: 'kN', area: 'm2' }, constraints: [],
    standards: [], claims: [], requested_output: 'pressure', validation_requirements: [],
  };
  const raw = JSON.stringify(value);
  const hash = crypto.createHash('sha256').update(raw).digest('hex');
  const incoming = path.join(root, 'incoming', hash);
  fs.mkdirSync(incoming, { recursive: true });
  fs.writeFileSync(path.join(incoming, 'package.json'), raw);
  return { request_key: crypto.randomBytes(32).toString('hex'), analysis_id: value.analysis_id,
    analysis_type: value.analysis_type, package_sha256: hash,
    incoming_relative_path: `incoming/${hash}/package.json` };
}

function child(list) {
  const value = new EventEmitter();
  value.kill = () => {};
  list.push(value);
  return value;
}

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'analysis-failure-'));
const children = [];
const queue = new AnalysisQueue({ spoolRoot: root, workerScript: 'x', workerRoot: root,
  spawnWorker: () => child(children) });

const ui = queue.create(fixture(root));
children[0].analysisOutput = 'WORKER_STATUS=UI_CHANGED';
children[0].emit('close', 21);
assert.strictEqual(queue.get(ui.job_id).state, 'UI_CHANGED');
assert.strictEqual(queue.health().browser.paused_state, 'UI_CHANGED');
queue.cancel(ui.job_id);
queue.resume();

const auth = queue.create(fixture(root));
children[1].analysisOutput = 'WORKER_STATUS=AUTH_REQUIRED';
children[1].emit('close', 20);
assert.strictEqual(queue.get(auth.job_id).state, 'AUTH_REQUIRED');
queue.resume();
setImmediate(() => {
  assert.strictEqual(children.length, 3);
  children[2].analysisOutput = 'WORKER_STATUS=AUTH_REQUIRED';
  children[2].emit('close', 20);
  assert.strictEqual(queue.get(auth.job_id).attempt_count, 2);
  queue.resume();
  setImmediate(() => {
    assert.strictEqual(children.length, 3);
    assert.strictEqual(queue.health().status, 'READY');
    fs.rmSync(root, { recursive: true, force: true });
    process.stdout.write('ANALYSIS AUTH/UI + RETRY BOUNDS: OK\n');
  });
});
