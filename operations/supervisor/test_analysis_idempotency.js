'use strict';

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { EventEmitter } = require('events');
const { AnalysisQueue } = require('./analysis_queue');

function stage(root, analysisId, problem) {
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
  return { value, hash, relative: `incoming/${hash}/package.json` };
}

function child(children) {
  const value = new EventEmitter();
  value.kill = () => {};
  children.push(value);
  return value;
}

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'analysis-idempotency-repro-'));
const children = [];
const queue = new AnalysisQueue({
  spoolRoot: root, workerScript: 'x', workerRoot: root,
  spawnWorker: () => child(children),
});
const requestKey = 'a'.repeat(64);
const oldId = crypto.randomUUID();
const oldPackage = stage(root, oldId, 'Synthetic shared formula.');
const oldJob = queue.create({ request_key: requestKey, analysis_id: oldId,
  analysis_type: 'formula_calculation', package_sha256: oldPackage.hash,
  incoming_relative_path: oldPackage.relative });
children[0].analysisOutput = 'TEMPORARY_CHAT_VERIFIED';
children[0].emit('close', 0);

setImmediate(() => {
  const newId = crypto.randomUUID();
  const newPackage = stage(root, newId, 'Synthetic shared formula.');
  const reused = queue.create({ request_key: requestKey, analysis_id: newId,
    analysis_type: 'formula_calculation', package_sha256: newPackage.hash,
    incoming_relative_path: newPackage.relative });
  assert.notStrictEqual(reused.job_id, oldJob.job_id, 'different analysis reused terminal job');
  console.log(`OLD_ANALYSIS_ID=${oldId}`);
  console.log(`NEW_ANALYSIS_ID=${newId}`);
  console.log(`SHARED_REQUEST_KEY=${requestKey}`);
  console.log(`OLD_PACKAGE_HASH=${oldPackage.hash}`);
  console.log(`NEW_PACKAGE_HASH=${newPackage.hash}`);
  console.log(`NEW_EXTERNAL_JOB=${reused.job_id}`);
  console.log(`TERMINAL_STATE=${reused.state}`);
  console.log('TERMINAL_CROSS_ANALYSIS_REUSE=0');
  fs.rmSync(root, { recursive: true, force: true });
});
