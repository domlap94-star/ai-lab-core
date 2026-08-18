'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

const TERMINAL = new Set(['COMPLETE', 'FAILED', 'CANCELLED']);
const MAX_BODY_BYTES = 64 * 1024;
const MAX_SOURCES = 4;
const MAX_SOURCE_BYTES = 15 * 1024 * 1024;
const RETRY_DELAYS = [0, 5 * 60 * 1000, 30 * 60 * 1000];

function safeWriteJson(filePath, value) {
  const temporary = `${filePath}.${process.pid}.tmp`;
  fs.writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
  fs.renameSync(temporary, filePath);
}

function within(root, candidate) {
  const resolvedRoot = `${fs.realpathSync(root)}${path.sep}`.toLowerCase();
  const resolved = fs.realpathSync(candidate).toLowerCase();
  return resolved.startsWith(resolvedRoot);
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

class VisionQueue {
  constructor({ spoolRoot, workerScript, workerRoot, spawnWorker } = {}) {
    this.spoolRoot = path.resolve(spoolRoot);
    this.jobsRoot = path.join(this.spoolRoot, 'jobs');
    this.incomingRoot = path.join(this.spoolRoot, 'incoming');
    this.workerScript = workerScript;
    this.workerRoot = workerRoot;
    this.spawnWorker = spawnWorker || this._spawnWorker.bind(this);
    this.queue = [];
    this.active = null;
    this.pausedState = null;
    fs.mkdirSync(this.jobsRoot, { recursive: true });
    fs.mkdirSync(this.incomingRoot, { recursive: true });
    this.recover();
  }

  recover() {
    for (const entry of fs.readdirSync(this.jobsRoot, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const statusPath = path.join(this.jobsRoot, entry.name, 'status.json');
      if (!fs.existsSync(statusPath)) continue;
      const status = readJson(statusPath);
      if (['QUEUED', 'RUNNING'].includes(status.state)) {
        status.state = 'QUEUED';
        status.error_code = null;
        safeWriteJson(statusPath, status);
        this.queue.push(entry.name);
      } else if (status.state === 'AUTH_REQUIRED' || status.state === 'UI_CHANGED') {
        this.pausedState = status.state;
      }
    }
    setImmediate(() => this.pump());
  }

  health() {
    return { status: this.pausedState || (this.active ? 'BUSY' : 'READY'), active_job_id: this.active ? this.active.jobId : null, queued: this.queue.length };
  }

  _existingByRequestKey(requestKey) {
    for (const entry of fs.readdirSync(this.jobsRoot, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const statusPath = path.join(this.jobsRoot, entry.name, 'status.json');
      if (!fs.existsSync(statusPath)) continue;
      const status = readJson(statusPath);
      if (status.request_key === requestKey) return status;
    }
    return null;
  }

  create(request) {
    if (!request || typeof request !== 'object' || Array.isArray(request)) throw new Error('INVALID_REQUEST');
    const requestFields = new Set(['request_key', 'sources']);
    if (Object.keys(request).some((key) => !requestFields.has(key))) throw new Error('INVALID_REQUEST_FIELD');
    const requestKey = String(request.request_key || '');
    if (!/^[a-f0-9]{64}$/i.test(requestKey)) throw new Error('INVALID_REQUEST_KEY');
    const existing = this._existingByRequestKey(requestKey);
    if (existing) {
      fs.rmSync(path.join(this.incomingRoot, requestKey), { recursive: true, force: true });
      return existing;
    }
    if (!Array.isArray(request.sources) || request.sources.length < 1 || request.sources.length > MAX_SOURCES) throw new Error('INVALID_SOURCES');
    const jobId = crypto.randomUUID();
    const jobDir = path.join(this.jobsRoot, jobId);
    fs.mkdirSync(path.join(jobDir, 'input'), { recursive: true });
    fs.mkdirSync(path.join(jobDir, 'output'), { recursive: true });
    const refs = new Set();
    const manifestSources = request.sources.map((source) => {
      if (!source || typeof source !== 'object') throw new Error('INVALID_SOURCE');
      const sourceFields = new Set([
        'source_ref', 'document_id', 'page_number', 'asset_id', 'sha256',
        'incoming_relative_path',
      ]);
      if (Object.keys(source).some((key) => !sourceFields.has(key))) throw new Error('INVALID_SOURCE_FIELD');
      const ref = String(source.source_ref || '');
      if (!/^S[1-4]$/.test(ref) || refs.has(ref)) throw new Error('INVALID_SOURCE_REF');
      refs.add(ref);
      if (!Number.isInteger(source.document_id) || source.document_id < 1) throw new Error('INVALID_DOCUMENT_ID');
      if (source.page_number != null && (!Number.isInteger(source.page_number) || source.page_number < 1)) throw new Error('INVALID_PAGE_NUMBER');
      if (source.asset_id != null && (!Number.isInteger(source.asset_id) || source.asset_id < 1)) throw new Error('INVALID_ASSET_ID');
      if (!/^[a-f0-9]{64}$/i.test(String(source.sha256 || ''))) throw new Error('INVALID_SOURCE_CHECKSUM');
      const relative = String(source.incoming_relative_path || '').replace(/\\/g, '/');
      if (!/^incoming\/[a-f0-9]{64}\/S[1-4]\.[a-z0-9]{1,8}$/i.test(relative)) throw new Error('INVALID_SOURCE_PATH');
      const inputPath = path.resolve(this.spoolRoot, ...relative.split('/'));
      if (!fs.existsSync(inputPath) || !fs.lstatSync(inputPath).isFile() || !within(this.spoolRoot, inputPath)) throw new Error('INVALID_SOURCE_PATH');
      if (fs.statSync(inputPath).size > MAX_SOURCE_BYTES) throw new Error('INVALID_SOURCE_SIZE');
      const actualHash = crypto.createHash('sha256').update(fs.readFileSync(inputPath)).digest('hex');
      if (actualHash !== source.sha256) throw new Error('SOURCE_CHECKSUM');
      const extension = path.extname(inputPath).toLowerCase();
      if (!/^\.[a-z0-9]{1,8}$/.test(extension)) throw new Error('INVALID_EXTENSION');
      const targetName = `${ref}${extension}`;
      fs.copyFileSync(inputPath, path.join(jobDir, 'input', targetName));
      return {
        source_ref: ref, document_id: source.document_id, page_number: source.page_number ?? null,
        asset_id: source.asset_id ?? null, sha256: actualHash, relative_input_path: `input/${targetName}`,
      };
    });
    const manifest = { schema_version: 'NEXT_STABIL_VISION_JOB_V1', job_id: jobId, analysis_goal: 'technical_visual_analysis', sources: manifestSources };
    safeWriteJson(path.join(jobDir, 'manifest.json'), manifest);
    const now = new Date().toISOString();
    const status = { job_id: jobId, request_key: requestKey, state: 'QUEUED', attempt_count: 0, error_code: null, created_at: now, updated_at: now, next_retry_at: null };
    safeWriteJson(path.join(jobDir, 'status.json'), status);
    fs.rmSync(path.join(this.incomingRoot, requestKey), { recursive: true, force: true });
    this.queue.push(jobId);
    this.pump();
    return status;
  }

  get(jobId) {
    if (!/^[a-f0-9-]{36}$/i.test(String(jobId || ''))) return null;
    const statusPath = path.join(this.jobsRoot, jobId, 'status.json');
    return fs.existsSync(statusPath) ? readJson(statusPath) : null;
  }

  cancel(jobId) {
    const status = this.get(jobId);
    if (!status) return null;
    if (this.active && this.active.jobId === jobId) {
      fs.writeFileSync(path.join(this.jobsRoot, jobId, 'cancel.requested'), '', 'utf8');
      const child = this.active.child;
      setTimeout(() => {
        if (this.active && this.active.jobId === jobId) child.kill();
      }, 10000).unref();
    }
    this.queue = this.queue.filter((item) => item !== jobId);
    return this._set(jobId, {
      state: 'CANCELLED',
      error_code: null,
      next_retry_at: null,
    });
  }

  resume() {
    this.pausedState = null;
    for (const entry of fs.readdirSync(this.jobsRoot, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const status = this.get(entry.name);
      if (status && ['AUTH_REQUIRED', 'UI_CHANGED'].includes(status.state) && status.attempt_count < 3) {
        this._set(entry.name, { state: 'QUEUED', error_code: null });
        this.queue.push(entry.name);
      }
    }
    this.pump();
    return this.health();
  }

  _set(jobId, patch) {
    const statusPath = path.join(this.jobsRoot, jobId, 'status.json');
    const current = readJson(statusPath);
    const next = { ...current, ...patch, updated_at: new Date().toISOString() };
    safeWriteJson(statusPath, next);
    return next;
  }

  async pump() {
    if (this.active || this.pausedState || this.queue.length === 0) return;
    const jobId = this.queue.shift();
    const current = this.get(jobId);
    if (!current || current.state !== 'QUEUED') return this.pump();
    const attempt = current.attempt_count + 1;
    this._set(jobId, { state: 'RUNNING', attempt_count: attempt, next_retry_at: null });
    const child = this.spawnWorker(path.join(this.jobsRoot, jobId));
    this.active = { jobId, child };
    child.on('close', (code) => {
      this.active = null;
      const latest = this.get(jobId);
      if (latest && latest.state === 'CANCELLED') {
        this.pump();
        return;
      }
      const text = String(child.visionOutput || '');
      if (code === 0) {
        let formatRetryUsed = null;
        const resultManifestPath = path.join(this.jobsRoot, jobId, 'output', 'result_manifest.json');
        if (fs.existsSync(resultManifestPath)) {
          const resultManifest = readJson(resultManifestPath);
          formatRetryUsed = Boolean(resultManifest.format_retry_used);
          this._set(jobId, { timings: resultManifest.timings || null });
        }
        this._set(jobId, {
          state: 'COMPLETE', error_code: null,
          temporary_chat_verified: text.includes('TEMPORARY_CHAT_VERIFIED'),
          upload_success: text.includes('UPLOAD_COMPLETE'),
          format_retry_used: formatRetryUsed,
        });
      } else if (code === 20 || text.includes('AUTH_REQUIRED')) {
        this.pausedState = 'AUTH_REQUIRED';
        this._set(jobId, { state: 'AUTH_REQUIRED', error_code: 'AUTH_REQUIRED' });
      } else if (code === 21 || text.includes('UI_CHANGED')) {
        this.pausedState = 'UI_CHANGED';
        this._set(jobId, { state: 'UI_CHANGED', error_code: 'UI_CHANGED' });
      } else if (attempt < 3) {
        const delay = RETRY_DELAYS[attempt];
        const nextRetry = new Date(Date.now() + delay).toISOString();
        const workerCode = /WORKER_ERROR_CODE=([A-Z0-9_:. -]{1,100})/.exec(text);
        this._set(jobId, { state: 'QUEUED', error_code: workerCode ? workerCode[1].trim() : 'WORKER_FAILED', next_retry_at: nextRetry });
        setTimeout(() => { this.queue.push(jobId); this.pump(); }, delay);
      } else {
        this._set(jobId, { state: 'FAILED', error_code: 'WORKER_FAILED' });
      }
      this.pump();
    });
  }

  _spawnWorker(jobDir) {
    const child = spawn(process.execPath, [this.workerScript, jobDir], {
      cwd: path.dirname(this.workerScript), windowsHide: false, shell: false,
      env: { ...process.env, NEXT_STABIL_VISION_WORKER_ROOT: this.workerRoot },
    });
    let output = '';
    child.stdout.on('data', (chunk) => { output += chunk.toString(); });
    child.stderr.on('data', (chunk) => { output += chunk.toString(); });
    child.on('close', () => { child.visionOutput = output; });
    return child;
  }

  cleanup(ttlMs = 72 * 60 * 60 * 1000) {
    const cutoff = Date.now() - ttlMs;
    let removed = 0;
    for (const entry of fs.readdirSync(this.jobsRoot, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const status = this.get(entry.name);
      if (!status || !TERMINAL.has(status.state) || Date.parse(status.updated_at) >= cutoff) continue;
      fs.rmSync(path.join(this.jobsRoot, entry.name), { recursive: true, force: true });
      removed += 1;
    }
    const converted = path.join(this.spoolRoot, 'converted');
    if (fs.existsSync(converted)) {
      for (const entry of fs.readdirSync(converted, { withFileTypes: true })) {
        const candidate = path.join(converted, entry.name);
        if (entry.isFile() && fs.statSync(candidate).mtimeMs < cutoff) {
          fs.rmSync(candidate, { force: true });
          removed += 1;
        }
      }
    }
    for (const entry of fs.readdirSync(this.incomingRoot, { withFileTypes: true })) {
      if (!entry.isDirectory() || !/^[a-f0-9]{64}$/i.test(entry.name)) continue;
      const candidate = path.join(this.incomingRoot, entry.name);
      if (fs.statSync(candidate).mtimeMs < cutoff) {
        fs.rmSync(candidate, { recursive: true, force: true });
        removed += 1;
      }
    }
    return removed;
  }
}

module.exports = { VisionQueue, MAX_BODY_BYTES, MAX_SOURCE_BYTES, within };
