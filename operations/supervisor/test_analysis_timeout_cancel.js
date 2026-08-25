'use strict';
const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { EventEmitter } = require('events');
const { AnalysisQueue } = require('./analysis_queue');

async function main() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'analysis-timeout-'));
  const pkg = {
    schema_version: 'NEXT_STABIL_ADVANCED_ANALYSIS_V1',
    analysis_id: crypto.randomUUID(),
    analysis_type: 'technical_interpretation',
    problem: 'Synthetic public fixture',
    sources: [{ source_ref: 'S1', source_sha256: 'c'.repeat(64), technical_excerpt: 'safe', page: 1 }],
    tables: [], formulas: [], variables: {}, values: {}, units: {}, constraints: [], standards: [], claims: [],
    requested_output: 'result', validation_requirements: [],
  };
  const raw = JSON.stringify(pkg);
  const hash = crypto.createHash('sha256').update(raw).digest('hex');
  const incoming = path.join(root, 'incoming', hash);
  fs.mkdirSync(incoming, { recursive: true });
  fs.writeFileSync(path.join(incoming, 'package.json'), raw);
  let killed = false;
  const child = new EventEmitter();
  child.kill = () => { killed = true; setImmediate(() => child.emit('close', 1)); };
  const queue = new AnalysisQueue({
    spoolRoot: root, workerScript: 'x', workerRoot: root,
    workerTimeoutMs: 20, spawnWorker: () => child,
  });
  const created = queue.create({
    request_key: 'a'.repeat(64), analysis_id: pkg.analysis_id,
    analysis_type: pkg.analysis_type, package_sha256: hash,
    incoming_relative_path: `incoming/${hash}/package.json`,
  });
  await new Promise((resolve) => setTimeout(resolve, 80));
  const status = queue.get(created.job_id);
  assert.strictEqual(killed, true);
  assert.strictEqual(status.state, 'FAILED');
  assert.strictEqual(status.current_stage, 'TIMED_OUT');
  assert.strictEqual(status.error_code, 'WORKER_TIMEOUT');
  fs.rmSync(root, { recursive: true, force: true });
  process.stdout.write('ANALYSIS TIMEOUT + CANCEL: OK\n');
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
