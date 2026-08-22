'use strict';

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { EventEmitter } = require('events');
const { AnalysisQueue } = require('./analysis_queue');

function stage(root, analysisId, problem = 'Synthetic shared formula.') {
  const value = {
    schema_version: 'NEXT_STABIL_ADVANCED_ANALYSIS_V1', analysis_id: analysisId,
    analysis_type: 'formula_calculation', problem,
    sources: [{ source_ref: 'S1', source_sha256: 'c'.repeat(64), technical_excerpt: 'P = F / A', page: 1 }],
    tables: [], formulas: ['force/area'], variables: { force: 10, area: .005 },
    values: { force: 10, area: .005 }, units: { force: 'kN', area: 'm2' },
    constraints: [], standards: [], claims: [], requested_output: 'Return MPa.',
    validation_requirements: [],
  };
  const raw = JSON.stringify(value);
  const hash = crypto.createHash('sha256').update(raw).digest('hex');
  const incoming = path.join(root, 'incoming', hash);
  fs.mkdirSync(incoming, { recursive: true });
  fs.writeFileSync(path.join(incoming, 'package.json'), raw);
  return { request_key: 'a'.repeat(64), analysis_id: analysisId,
    analysis_type: 'formula_calculation', package_sha256: hash,
    incoming_relative_path: `incoming/${hash}/package.json` };
}

function child(children) {
  const value = new EventEmitter();
  value.kill = () => {};
  children.push(value);
  return value;
}

const tick = () => new Promise(resolve => setImmediate(resolve));

async function main() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'analysis-idempotency-matrix-'));
  const children = [];
  try {
    const queue = new AnalysisQueue({ spoolRoot: root, workerScript: 'x', workerRoot: root,
      spawnWorker: () => child(children) });
    const a1 = crypto.randomUUID();
    const r1 = stage(root, a1);
    const j1 = queue.create(r1);
    assert.strictEqual(queue.create(r1).job_id, j1.job_id);
    assert.strictEqual(children.length, 1, 'running same-analysis retry duplicated');
    children[0].analysisOutput = 'TEMPORARY_CHAT_VERIFIED'; children[0].emit('close', 0);
    await tick();
    assert.strictEqual(queue.create(r1).job_id, j1.job_id, 'terminal same-analysis retry duplicated');
    const changed = stage(root, a1, 'Changed immutable package.');
    assert.throws(() => queue.create(changed), /IDEMPOTENCY_CONFLICT/);

    const a2 = crypto.randomUUID();
    const r2 = stage(root, a2);
    const j2 = queue.create(r2);
    assert.notStrictEqual(j2.job_id, j1.job_id, 'different analysis reused terminal job');
    const queuedId = crypto.randomUUID();
    const queuedRequest = { ...stage(root, queuedId), request_key: 'b'.repeat(64) };
    const queued = queue.create(queuedRequest);
    assert.strictEqual(queue.get(queued.job_id).state, 'QUEUED');
    assert.strictEqual(queue.create(queuedRequest).job_id, queued.job_id);
    children[1].analysisOutput = 'WORKER_ERROR_CODE=SYNTHETIC_FAILURE'; children[1].emit('close', 1);
    await tick();
    assert.strictEqual(queue.get(j2.job_id).state, 'FAILED');
    children[2].analysisOutput = 'TEMPORARY_CHAT_VERIFIED'; children[2].emit('close', 0);
    await tick();

    const a3 = crypto.randomUUID();
    const r3 = stage(root, a3);
    const j3 = queue.create(r3);
    assert.notStrictEqual(j3.job_id, j2.job_id, 'different analysis inherited failed job');
    children[3].analysisOutput = 'AUTH_REQUIRED'; children[3].emit('close', 20);
    await tick();
    assert.strictEqual(queue.create(r3).job_id, j3.job_id, 'AUTH_REQUIRED retry duplicated');
    queue.resume(); await tick();
    children[4].analysisOutput = 'TEMPORARY_CHAT_VERIFIED'; children[4].emit('close', 0);
    await tick();
    assert.strictEqual(queue.get(j3.job_id).state, 'COMPLETE');
    console.log('SAME_ANALYSIS_SAME_PACKAGE=IDEMPOTENT');
    console.log('DIFFERENT_ANALYSIS_SAME_REQUEST_KEY=NEW_JOB');
    console.log('SAME_ANALYSIS_DIFFERENT_PACKAGE=CONFLICT');
    console.log('QUEUED_RUNNING_TERMINAL_REUSE=BOUND_SAFE');
    console.log('AUTH_REQUIRED_RESUME=SAME_JOB');
    console.log('FAILED_TERMINAL_CROSS_ANALYSIS_REUSE=0');
    console.log('ANALYSIS IDEMPOTENCY MATRIX: OK');
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
