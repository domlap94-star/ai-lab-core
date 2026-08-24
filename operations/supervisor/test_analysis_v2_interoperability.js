'use strict';

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { EventEmitter } = require('events');
const { AnalysisQueue, verifyV2Output } = require('./analysis_queue');
const { CONTRACT_V2, validatePackage, validateV2Result } = require('../vision-worker/analysis_contract');
const {
  parseV2, parseV2WithRetry, promptForV2, retryPromptV2, writeResult,
} = require('../vision-worker/analysis-job');

function packageFor(analysisId) {
  return {
    schema_version: 'NEXT_STABIL_ADVANCED_ANALYSIS_V1',
    analysis_id: analysisId,
    analysis_type: 'technical_interpretation',
    contract_version: CONTRACT_V2,
    problem: 'Synthetic public-safe question',
    sources: [{ source_ref: 'S1', source_sha256: 'c'.repeat(64), technical_excerpt: 'Fact one.', page: 1 }],
    tables: [], formulas: [], variables: {}, values: {}, units: {}, constraints: [], standards: [],
    claims: [
      { kind: 'FACT', fact_handle: 'F1', source_handle: 'S1', statement: 'Fact one.' },
      { kind: 'TOOL_RESULT', tool_handle: 'T1', source_handle: 'S1', statement: '10 mm' },
      { kind: 'VISUAL_OBSERVATION', visual_handle: 'V1', source_handles: ['S1'], statement: 'Public-safe observation.' },
    ],
    requested_output: 'Strict V2', validation_requirements: [],
  };
}

function result() {
  return {
    schema: CONTRACT_V2,
    claims: [{ class: 'FACT', fact_handles: ['F1'], tool_handles: ['T1'], visual_handles: [] }],
    contradictions: [],
  };
}

function manifest(jobId = crypto.randomUUID(), analysisId = crypto.randomUUID()) {
  return {
    job_id: jobId, analysis_id: analysisId, package_sha256: 'a'.repeat(64),
    package: packageFor(analysisId),
  };
}

const m = manifest();
const prompt = promptForV2(m);
assert(prompt.lastIndexOf('OSTATECZNY KONTRAKT ODPOWIEDZI') > prompt.lastIndexOf('PAKIET_DANYCH_END'));
assert.match(prompt, /WYŁĄCZNIE jeden maszynowo czytelny obiekt JSON/);
assert.match(prompt, /struktury V1, claim_id/);
assert.doesNotMatch(retryPromptV2(), /NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1/);

assert.deepStrictEqual(parseV2(JSON.stringify(result()), m), result());
assert.deepStrictEqual(parseV2(`\`\`\`json\n${JSON.stringify(result())}\n\`\`\``, m), result());
assert.throws(() => parseV2(`tekst ${JSON.stringify(result())}`, m), /V2_MALFORMED_JSON/);
assert.throws(() => parseV2('{', m), /V2_MALFORMED_JSON/);
assert.deepStrictEqual(parseV2WithRetry('legacy prose', JSON.stringify(result()), m), { result: result(), retry_used: true });
assert.throws(() => parseV2WithRetry('legacy prose', 'still invalid', m), /V2_MALFORMED_JSON/);
assert.throws(() => parseV2(JSON.stringify({ ...result(), schema: 'NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1' }), m), /V2_SCHEMA/);
assert.throws(() => validateV2Result({ ...result(), claims: [{ class: 'FACT', fact_handles: ['F9'], tool_handles: [], visual_handles: [] }] }, m), /V2_UNKNOWN_FACT/);
assert.throws(() => validateV2Result({ ...result(), claims: [{ class: 'FACT', claim_id: 'external', fact_handles: ['F1'], tool_handles: [], visual_handles: [] }] }, m), /V2_EXTERNAL_CLAIM_ID/);

const scoped = packageFor(m.analysis_id);
scoped.sources.push({ source_ref: 'S2', source_sha256: 'd'.repeat(64), technical_excerpt: 'Fact two.', page: 1 });
scoped.claims.push(
  { kind: 'FACT', fact_handle: 'F2', source_handle: 'S2', statement: 'Fact two.' },
  { kind: 'TOOL_RESULT', tool_handle: 'T2', source_handles: ['S2'], statement: '20 mm' },
  { kind: 'VISUAL_OBSERVATION', visual_handle: 'V2', source_handles: ['S2'], statement: 'Other scope.' },
);
scoped.target_scope = { scope_handle: 'TARGET_01', allowed_source_handles: ['S1'], global_source_handles: [] };
const scopedManifest = { ...m, package: scoped };
validatePackage(scoped);
assert.deepStrictEqual(validateV2Result(result(), scopedManifest), result());
assert.throws(() => validateV2Result({ ...result(), claims: [{ class: 'FACT', fact_handles: ['F2'], tool_handles: [], visual_handles: [] }] }, scopedManifest), /V2_UNKNOWN_FACT/);
assert.throws(() => validateV2Result({ ...result(), claims: [{ class: 'FACT', fact_handles: [], tool_handles: ['T2'], visual_handles: [] }] }, scopedManifest), /V2_UNKNOWN_TOOL/);
assert.throws(() => validateV2Result({ ...result(), claims: [{ class: 'FACT', fact_handles: [], tool_handles: [], visual_handles: ['V2'] }] }, scopedManifest), /V2_UNKNOWN_VISUAL/);

const estimable = { schema: CONTRACT_V2, claims: [{ class: 'ESTIMATE', estimate_status: 'ESTIMABLE', value_or_range: '8-12 mm', confidence: 'MEDIUM', basis_fact_handles: ['F1'], basis_tool_handles: [], assumptions: [], missing_inputs: [] }], contradictions: [] };
const notEstimable = { schema: CONTRACT_V2, claims: [{ class: 'ESTIMATE', estimate_status: 'NOT_ESTIMABLE', reason: 'Brak danych.', basis_fact_handles: ['F1'], basis_tool_handles: [], missing_inputs: ['pomiar'] }], contradictions: [] };
validateV2Result(estimable, scopedManifest);
validateV2Result(notEstimable, scopedManifest);
assert.throws(() => validateV2Result({ ...notEstimable, claims: [{ ...notEstimable.claims[0], confidence: 'LOW' }] }, scopedManifest), /V2_CLAIM_SCHEMA/);
assert.throws(() => validateV2Result({ ...notEstimable, claims: [{ ...notEstimable.claims[0], value_or_range: '10 mm' }] }, scopedManifest), /V2_CLAIM_SCHEMA/);
assert.throws(() => validatePackage({ ...scoped, target_scope: { scope_handle: 'TARGET_01', allowed_source_handles: ['S2', 'S2'], global_source_handles: [] } }), /V2_TARGET_SCOPE/);

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'analysis-v2-interoperability-'));
try {
  const jobDir = path.join(root, 'artifact');
  fs.mkdirSync(jobDir, { recursive: true });
  writeResult(jobDir, m, result(), JSON.stringify(result()), false);
  assert.strictEqual(verifyV2Output(jobDir, m), true);
  assert.strictEqual(fs.readdirSync(path.join(jobDir, 'output')).some((name) => name.endsWith('.tmp')), false);

  const wrongJob = { ...m, job_id: crypto.randomUUID() };
  assert.throws(() => verifyV2Output(jobDir, wrongJob), /V2_RESULT_BINDING/);
  const wrongRequest = { ...m, analysis_id: crypto.randomUUID() };
  assert.throws(() => verifyV2Output(jobDir, wrongRequest), /V2_RESULT_BINDING/);

  const staleDir = path.join(root, 'stale-copy');
  fs.mkdirSync(staleDir, { recursive: true });
  fs.cpSync(path.join(jobDir, 'output'), path.join(staleDir, 'output'), { recursive: true });
  assert.throws(() => verifyV2Output(staleDir, manifest()), /V2_RESULT_BINDING/);

  const partialDir = path.join(root, 'partial');
  fs.mkdirSync(path.join(partialDir, 'output'), { recursive: true });
  fs.writeFileSync(path.join(partialDir, 'output', 'analysis.json.partial.tmp'), '{');
  assert.throws(() => verifyV2Output(partialDir, m), /V2_RESULT_MISSING/);

  const queueRoot = path.join(root, 'queue');
  const pkg = packageFor(m.analysis_id);
  const raw = JSON.stringify(pkg);
  const hash = crypto.createHash('sha256').update(raw).digest('hex');
  const incoming = path.join(queueRoot, 'incoming', hash);
  fs.mkdirSync(incoming, { recursive: true });
  fs.writeFileSync(path.join(incoming, 'package.json'), raw);
  const children = [];
  const queue = new AnalysisQueue({
    spoolRoot: queueRoot, workerScript: 'x', workerRoot: root,
    spawnWorker: () => { const child = new EventEmitter(); child.kill = () => {}; children.push(child); return child; },
  });
  const created = queue.create({ request_key: 'b'.repeat(64), analysis_id: m.analysis_id,
    analysis_type: pkg.analysis_type, package_sha256: hash, contract_version: CONTRACT_V2,
    incoming_relative_path: `incoming/${hash}/package.json` });
  assert.strictEqual(created.contract_version, CONTRACT_V2);
  const queueManifest = JSON.parse(fs.readFileSync(path.join(queueRoot, 'jobs', created.job_id, 'manifest.json')));
  writeResult(path.join(queueRoot, 'jobs', created.job_id), queueManifest, result(), JSON.stringify(result()), false);
  children[0].analysisOutput = 'TEMPORARY_CHAT_VERIFIED';
  children[0].emit('close', 0);
  assert.strictEqual(queue.get(created.job_id).state, 'COMPLETE');

  const staleAnalysisId = crypto.randomUUID();
  const stalePkg = packageFor(staleAnalysisId); const staleRaw = JSON.stringify(stalePkg);
  const staleHash = crypto.createHash('sha256').update(staleRaw).digest('hex');
  const staleIncoming = path.join(queueRoot, 'incoming', staleHash);
  fs.mkdirSync(staleIncoming, { recursive: true }); fs.writeFileSync(path.join(staleIncoming, 'package.json'), staleRaw);
  const staleCreated = queue.create({ request_key: 'd'.repeat(64), analysis_id: staleAnalysisId,
    analysis_type: stalePkg.analysis_type, package_sha256: staleHash, contract_version: CONTRACT_V2,
    incoming_relative_path: `incoming/${staleHash}/package.json` });
  const staleJobDir = path.join(queueRoot, 'jobs', staleCreated.job_id);
  const staleManifest = JSON.parse(fs.readFileSync(path.join(staleJobDir, 'manifest.json')));
  writeResult(staleJobDir, staleManifest, result(), JSON.stringify(result()), false);
  // This fixture proves a pre-existing result cannot be adopted by a queued retry.
  queue._set(staleCreated.job_id, { state: 'QUEUED' }); queue.active = null; queue._start(staleCreated.job_id);
  assert.strictEqual(queue.get(staleCreated.job_id).error_code, 'STALE_RESULT');
} finally {
  fs.rmSync(root, { recursive: true, force: true });
}

process.stdout.write('TEMP_CHAT_V2_INTEROPERABILITY_OFFLINE=PASS\n');
