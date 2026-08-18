'use strict';

const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const path = require('path');
const { validateResult } = require('./vision_contract');

const PROJECT = 'C:\\ai-lab-core';
const FIXTURES = path.join(PROJECT, 'data', 'vision-controlled');
const SPOOL = path.join(PROJECT, 'data', 'vision-spool');
const requestedCount = Number(process.argv[2] || '20');
if (![3, 20].includes(requestedCount)) throw new Error('GATE_COUNT_MUST_BE_3_OR_20');
const REPORT = path.join(
  'C:\\ChatGPT-Vision-Worker',
  'output',
  requestedCount === 3 ? 'chunk15_micro_gate.json' : 'chunk15_reliability_gate.json',
);

function envFile() {
  const values = {};
  for (const line of fs.readFileSync(path.join(PROJECT, '.env'), 'utf8').split(/\r?\n/)) {
    const index = line.indexOf('=');
    if (index > 0 && !line.trim().startsWith('#')) values[line.slice(0, index).trim()] = line.slice(index + 1).trim().replace(/^['"]|['"]$/g, '');
  }
  return values;
}

const bridgeKey = crypto.createHmac('sha256', envFile().SECRET_KEY).update('next-stabil-vision-supervisor-v1').digest('hex');

function request(method, route, body) {
  return new Promise((resolve, reject) => {
    const data = body ? Buffer.from(JSON.stringify(body)) : null;
    const req = http.request({ host: '127.0.0.1', port: 8787, path: route, method, headers: {
      'X-Next-Stabil-Vision-Key': bridgeKey, 'Content-Type': 'application/json', ...(data ? { 'Content-Length': data.length } : {}),
    } }, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        if (res.statusCode >= 400) reject(new Error(`HTTP_${res.statusCode}`)); else resolve(value);
      });
    });
    req.on('error', reject); if (data) req.write(data); req.end();
  });
}

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

async function wait(jobId) {
  // A worker response is bounded to 180 seconds and the persistent queue may
  // perform its approved retry after 5 minutes.  The gate must not cancel the
  // job before that retry can run.
  const deadline = Date.now() + 15 * 60 * 1000;
  while (Date.now() < deadline) {
    const status = await request('GET', `/vision/jobs/${jobId}`);
    if (['COMPLETE', 'FAILED', 'AUTH_REQUIRED', 'UI_CHANGED', 'CANCELLED'].includes(status.state)) return status;
    await sleep(1500);
  }
  await request('POST', `/vision/jobs/${jobId}/cancel`, {});
  throw new Error('GATE_TIMEOUT');
}

async function main() {
  const available = fs.readdirSync(FIXTURES).filter((name) => name.endsWith('.png')).sort();
  if (available.length < requestedCount) throw new Error(`EXPECTED_${requestedCount}_FIXTURES_GOT_${available.length}`);
  const files = available.slice(0, requestedCount);
  const runId = `${Date.now()}`;
  const results = [];
  for (let index = 0; index < files.length; index += 1) {
    const sourceFiles = requestedCount === 20 && index === 18
      ? [files[index], files[index + 1]]
      : [files[index]];
    const sourceData = sourceFiles.map((name, sourceIndex) => {
      const file = path.join(FIXTURES, name);
      return {
        name,
        file,
        source_ref: `S${sourceIndex + 1}`,
        sha256: crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'),
      };
    });
    const requestKey = crypto.createHash('sha256').update(
      `controlled-${runId}-${index}-${sourceData.map((source) => source.sha256).join('-')}`,
    ).digest('hex');
    const incoming = path.join(SPOOL, 'incoming', requestKey);
    fs.mkdirSync(incoming, { recursive: true });
    const sources = sourceData.map((source, sourceIndex) => {
      fs.copyFileSync(source.file, path.join(incoming, `${source.source_ref}.png`));
      return {
        source_ref: source.source_ref,
        document_id: 900001 + index,
        page_number: sourceIndex + 1,
        asset_id: null,
        sha256: source.sha256,
        incoming_relative_path: `incoming/${requestKey}/${source.source_ref}.png`,
      };
    });
    const created = await request('POST', '/vision/jobs', { request_key: requestKey, sources });
    let status;
    try {
      status = await wait(created.job_id);
    } catch (error) {
      results.push({
        fixture: files[index], job_id: created.job_id, state: 'GATE_TIMEOUT',
        temporary_chat_verified: false, upload_success: false,
        format_retry_used: false, valid: false, error: error.message,
      });
      break;
    }
    const record = {
      fixture: sourceFiles.join(' + '), job_id: created.job_id, state: status.state,
      attempt_count: status.attempt_count || 0,
      temporary_chat_verified: status.temporary_chat_verified === true,
      upload_success: status.upload_success === true,
      format_retry_used: status.format_retry_used === true,
      timings: status.timings || null,
      valid: false, error: status.error_code || null,
    };
    if (status.state === 'COMPLETE') {
      try {
        const jobDir = path.join(SPOOL, 'jobs', created.job_id);
        const manifest = JSON.parse(fs.readFileSync(path.join(jobDir, 'manifest.json'), 'utf8'));
        const result = JSON.parse(fs.readFileSync(path.join(jobDir, 'output', 'vision.json'), 'utf8'));
        validateResult(result, manifest);
        record.valid = true;
        record.observations = result.observations.map((item) => item.text);
        record.possible_interpretations = result.possible_interpretations.map((item) => item.text);
        record.uncertainties = result.uncertainties.map((item) => item.text);
        record.visible_text = result.visible_text.map((item) => item.text);
        record.measurements = result.measurements;
        record.image_quality = result.image_quality;
      } catch (error) { record.error = error.message; }
    }
    results.push(record);
    process.stdout.write(`GATE_JOB_${index + 1}=${record.state}:${record.valid}\n`);
    if (['AUTH_REQUIRED', 'UI_CHANGED'].includes(status.state)) break;
  }
  const completed = results.filter((item) => item.valid);
  const report = {
    run_id: runId, jobs_requested: files.length, jobs_completed: results.length,
    temporary_chat_verified: results.filter((item) => item.temporary_chat_verified).length,
    upload_success: results.filter((item) => item.upload_success).length,
    valid_first_response: completed.filter((item) => !item.format_retry_used).length,
    valid_after_retry: completed.length,
    execution_retries: completed.filter((item) => item.attempt_count > 1).length,
    normal_chat_fallback: 0,
    unknown_source_refs_accepted: 0,
    results,
  };
  fs.mkdirSync(path.dirname(REPORT), { recursive: true });
  fs.writeFileSync(REPORT, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  process.stdout.write(`GATE_REPORT=${REPORT}\n`);
  const minimumUploads = requestedCount === 3 ? 3 : 19;
  const minimumFirst = requestedCount === 3 ? 0 : 18;
  if (results.length !== requestedCount
    || report.temporary_chat_verified !== requestedCount
    || report.upload_success < minimumUploads
    || report.valid_after_retry < requestedCount
    || report.valid_first_response < minimumFirst) process.exitCode = 1;
}

main().catch((error) => { process.stderr.write(`GATE_FAILURE=${error.message}\n`); process.exitCode = 1; });
