'use strict';

const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { VisionQueue, MAX_BODY_BYTES } = require('./vision_queue');
const { validateQdrantSnapshot } = require('./qdrant_snapshot_validator');

const qdrantSnapshotValidationCache = new Map();

const HOST = '127.0.0.1';
const PORT = Number(process.env.AI_LAB_SUPERVISOR_PORT || '8787');
const PROJECT_DIR = process.env.AI_LAB_PROJECT_DIR || 'C:\\ai-lab-core';
const ENV_FILE = path.join(PROJECT_DIR, '.env');
const VISION_SPOOL = path.join(PROJECT_DIR, 'data', 'vision-spool');
const VISION_WORKER_ROOT = process.env.NEXT_STABIL_VISION_WORKER_ROOT || 'C:\\ChatGPT-Vision-Worker';
const VISION_WORKER_SCRIPT = process.env.NEXT_STABIL_VISION_WORKER_SCRIPT || path.join(VISION_WORKER_ROOT, 'worker', 'vision-job.js');

const CORE_SERVICES = [
  'postgres',
  'qdrant',
  'ollama',
  'backend',
  'n8n',
  'open-webui',
];

function loadEnvFile(filePath) {
  const result = {};

  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing .env file: ${filePath}`);
  }

  const content = fs.readFileSync(filePath, 'utf8');

  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();

    if (!line || line.startsWith('#')) {
      continue;
    }

    const index = line.indexOf('=');

    if (index <= 0) {
      continue;
    }

    const key = line.slice(0, index).trim();
    let value = line.slice(index + 1).trim();

    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }

    result[key] = value;
  }

  return result;
}

const env = loadEnvFile(ENV_FILE);
const SECRET_KEY = env.SECRET_KEY || env.secret_key;
const ALGORITHM = env.ALGORITHM || env.algorithm || 'HS256';

if (!SECRET_KEY) {
  throw new Error('SECRET_KEY is missing from project .env');
}

if (ALGORITHM !== 'HS256') {
  throw new Error(`Unsupported JWT algorithm: ${ALGORITHM}`);
}

const VISION_BRIDGE_KEY = crypto
  .createHmac('sha256', SECRET_KEY)
  .update('next-stabil-vision-supervisor-v1')
  .digest('hex');

const BACKUP_BRIDGE_KEY = crypto
  .createHmac('sha256', SECRET_KEY)
  .update('next-stabil-backup-supervisor-v1')
  .digest('hex');
const BACKUP_SCRIPT = path.join(PROJECT_DIR, 'operations', 'hardening', 'backup-production.ps1');
const DEFAULT_BACKUP_ROOT = 'C:\\ai-lab-core-backups';
const BACKUP_SCOPES = new Set(['full', 'database', 'documents', 'qdrant', 'n8n_config']);
const BACKUP_STAGES = new Set(['validating', 'database', 'documents', 'qdrant', 'n8n', 'configuration', 'release', 'verifying']);
const backupOperations = new Map();
let activeBackupOperationId = null;

const visionQueue = new VisionQueue({
  spoolRoot: VISION_SPOOL,
  workerScript: VISION_WORKER_SCRIPT,
  workerRoot: VISION_WORKER_ROOT,
});

function authorizeVision(req) {
  const supplied = Buffer.from(String(req.headers['x-next-stabil-vision-key'] || ''), 'utf8');
  const expected = Buffer.from(VISION_BRIDGE_KEY, 'utf8');
  if (supplied.length !== expected.length || !crypto.timingSafeEqual(supplied, expected)) {
    throw new Error('Unauthorized');
  }
}

function authorizeBackup(req) {
  const supplied = Buffer.from(String(req.headers['x-next-stabil-backup-key'] || ''), 'utf8');
  const expected = Buffer.from(BACKUP_BRIDGE_KEY, 'utf8');
  if (supplied.length !== expected.length || !crypto.timingSafeEqual(supplied, expected)) {
    throw new Error('Unauthorized');
  }
}

function validateBackupDestination(value) {
  const raw = String(value || '').trim().replace(/\//g, '\\');
  if (!/^[A-Za-z]:\\/.test(raw) || raw.split('\\').includes('..')) {
    throw new Error('backup_destination_invalid');
  }
  const resolved = path.win32.resolve(raw).replace(/[\\]+$/, '');
  const lower = resolved.toLowerCase();
  const repo = path.win32.resolve(PROJECT_DIR).replace(/[\\]+$/, '').toLowerCase();
  const data = path.win32.join(repo, 'data').toLowerCase();
  if (lower === repo || lower.startsWith(`${repo}\\`) || lower === data || lower.startsWith(`${data}\\`)) {
    throw new Error('backup_destination_active_path');
  }
  return resolved;
}

function safeJoinCheckpoint(checkpoint, relative) {
  if (typeof relative !== 'string' || !relative || path.win32.isAbsolute(relative)) {
    throw new Error('backup_manifest_artifact_path_invalid');
  }
  const base = path.win32.resolve(checkpoint);
  const target = path.win32.resolve(base, relative.replace(/\//g, '\\'));
  if (!target.toLowerCase().startsWith(`${base.toLowerCase()}\\`)) {
    throw new Error('backup_manifest_artifact_path_invalid');
  }
  return target;
}

function hashFile(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256');
    const stream = fs.createReadStream(filePath);
    stream.on('error', reject);
    stream.on('data', (chunk) => hash.update(chunk));
    stream.on('end', () => resolve(hash.digest('hex')));
  });
}

function compareVersion(left, right) {
  const parse = (value) => String(value || '').split('+')[0].split('.').map(Number);
  const a = parse(left); const b = parse(right);
  if (a.length !== 3 || b.length !== 3 || [...a, ...b].some((item) => !Number.isInteger(item))) return null;
  for (let index = 0; index < 3; index += 1) {
    if (a[index] !== b[index]) return a[index] < b[index] ? -1 : 1;
  }
  return 0;
}

async function verifyCheckpoint(checkpoint) {
  const manifestPath = path.win32.join(checkpoint, 'backup-manifest.json');
  if (!fs.existsSync(manifestPath)) throw new Error('backup_manifest_missing');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8').replace(/^\uFEFF/, ''));
  if (manifest.schema_version !== 'NEXT_STABIL_BACKUP_V1' || !Array.isArray(manifest.artifacts)) {
    throw new Error('backup_manifest_invalid');
  }
  let totalBytes = 0;
  const components = [];
  for (const artifact of manifest.artifacts) {
    const filePath = safeJoinCheckpoint(checkpoint, artifact.file);
    const stats = fs.statSync(filePath);
    if (!stats.isFile() || Number(artifact.bytes) !== stats.size) throw new Error('backup_artifact_size_mismatch');
    if ((await hashFile(filePath)).toLowerCase() !== String(artifact.sha256 || '').toLowerCase()) {
      throw new Error('backup_artifact_hash_mismatch');
    }
    totalBytes += stats.size;
    components.push(path.win32.basename(filePath));
  }
  const currentManifest = JSON.parse(fs.readFileSync(path.join(PROJECT_DIR, 'release-channel', 'stable', 'manifest.json'), 'utf8').replace(/^\uFEFF/, ''));
  const backupVersion = String(manifest.app_version || manifest.release || '');
  const versionComparison = compareVersion(backupVersion, currentManifest.version);
  const currentDbRevision = String(process.env.NEXT_STABIL_DB_REVISION || 'followup_admin_backup_restore_ui_20260821');
  let compatibility = 'compatible';
  if (versionComparison === null) compatibility = 'invalid';
  else if (versionComparison > 0) compatibility = 'newer_unsupported_checkpoint';
  else if (String(manifest.db_revision || '') !== currentDbRevision) compatibility = 'older_supported_checkpoint';
  const names = new Set(components);
  const databaseEligible = names.has('postgres.dump');
  const fullRequired = ['postgres.dump', 'document-storage.tar.gz', 'release-stable.tar.gz', 'qdrant.snapshot', 'n8n-workflows.json', 'n8n-credentials.encrypted.json', 'configuration.tar.gz'];
  const fullArtifactsPresent = fullRequired.every((name) => names.has(name));
  let qdrantSnapshotStructurallyValid = false;
  let qdrantSnapshotValidationReason = null;
  if (names.has('qdrant.snapshot')) {
    const qdrantArtifact = manifest.artifacts.find((artifact) => path.win32.basename(String(artifact.file || '')) === 'qdrant.snapshot');
    if (qdrantArtifact) {
      const qdrantPath = safeJoinCheckpoint(checkpoint, qdrantArtifact.file);
      const stats = fs.statSync(qdrantPath);
      const cacheKey = `${qdrantPath.toLowerCase()}|${stats.size}|${stats.mtimeMs}`;
      let structural = qdrantSnapshotValidationCache.get(cacheKey);
      if (!structural) {
        structural = await validateQdrantSnapshot(qdrantPath);
        if (qdrantSnapshotValidationCache.size >= 200) {
          qdrantSnapshotValidationCache.delete(qdrantSnapshotValidationCache.keys().next().value);
        }
        qdrantSnapshotValidationCache.set(cacheKey, structural);
      }
      qdrantSnapshotStructurallyValid = structural.valid === true;
      qdrantSnapshotValidationReason = structural.reason || null;
    }
  }
  const qdrantRestoreVerified = manifest.qdrant_restore_verified === true;
  const fullEligible = fullArtifactsPresent && qdrantSnapshotStructurallyValid && qdrantRestoreVerified;
  let restoreErrorCode = null;
  if (fullArtifactsPresent && !qdrantSnapshotStructurallyValid) restoreErrorCode = 'qdrant_snapshot_invalid';
  else if (fullArtifactsPresent && !qdrantRestoreVerified) {
    restoreErrorCode = String(manifest.qdrant_restore_error_code || 'qdrant_restore_verification_required');
  }
  return {
    checkpoint_path: checkpoint,
    created_at: manifest.created_at,
    scope: manifest.scope || 'full',
    app_version: backupVersion,
    source_head: String(manifest.source_head || ''),
    db_revision: String(manifest.db_revision || ''),
    total_bytes: totalBytes,
    verified: true,
    artifact_count: manifest.artifacts.length,
    components,
    database_eligible: databaseEligible,
    full_eligible: fullEligible,
    qdrant_snapshot_structurally_valid: qdrantSnapshotStructurallyValid,
    qdrant_snapshot_validation_reason: qdrantSnapshotValidationReason,
    compatibility,
    error_code: restoreErrorCode,
    manifest_path: manifestPath,
  };
}

async function discoverCheckpoints(destinations) {
  const items = [];
  for (const raw of destinations.slice(0, 10)) {
    const root = validateBackupDestination(raw);
    if (!fs.existsSync(root)) continue;
    const children = fs.readdirSync(root, { withFileTypes: true })
      .filter((item) => item.isDirectory())
      .sort((a, b) => b.name.localeCompare(a.name))
      .slice(0, 100);
    for (const child of children) {
      const checkpoint = path.win32.join(root, child.name);
      try {
        items.push(await verifyCheckpoint(checkpoint));
      } catch (_) {
        // Invalid directories are not exposed as restore candidates.
      }
    }
  }
  return items.sort((a, b) => String(b.created_at).localeCompare(String(a.created_at))).slice(0, 100);
}

function startBackupOperation(payload) {
  if (activeBackupOperationId) throw new Error('backup_already_running');
  const scope = String(payload.scope || '');
  if (!BACKUP_SCOPES.has(scope)) throw new Error('backup_scope_invalid');
  const destination = validateBackupDestination(payload.destination);
  const release = String(payload.release || '');
  if (!/^\d+\.\d+\.\d+\+\d+$/.test(release)) throw new Error('backup_release_invalid');
  const runId = Number(payload.run_id);
  if (!Number.isSafeInteger(runId) || runId <= 0) throw new Error('backup_run_id_invalid');
  const operationId = crypto.randomUUID();
  const operation = {
    operation_id: operationId, status: 'running', stage: 'validating',
    checkpoint_path: null, manifest_path: null, artifact_count: 0,
    total_bytes: 0, verified: false, error_code: null,
  };
  backupOperations.set(operationId, operation);
  activeBackupOperationId = operationId;
  const args = [
    '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', BACKUP_SCRIPT,
    '-RepositoryRoot', PROJECT_DIR, '-BackupRoot', destination, '-Release', release,
    '-QdrantCollection', 'ai_lab_document_chunks', '-Scope', scope,
    '-RunId', String(runId), '-Trigger', 'manual',
  ];
  const child = spawn('powershell.exe', args, { cwd: PROJECT_DIR, windowsHide: true, shell: false });
  let stdout = ''; let stderr = '';
  child.stdout.on('data', (chunk) => {
    stdout += chunk.toString();
    const matches = stdout.match(/BACKUP_STAGE=([a-z_]+)/g) || [];
    if (matches.length) {
      const stage = matches[matches.length - 1].split('=')[1];
      if (BACKUP_STAGES.has(stage)) operation.stage = stage;
    }
  });
  child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
  child.on('error', () => {
    operation.status = 'failed'; operation.stage = 'failed'; operation.error_code = 'backup_runner_start_failed';
    activeBackupOperationId = null;
  });
  child.on('close', async (code) => {
    try {
      if (code !== 0) throw new Error('backup_runner_failed');
      const checkpointMatch = /BACKUP_COMPLETE=(.+)/.exec(stdout);
      if (!checkpointMatch) throw new Error('backup_checkpoint_missing');
      const verified = await verifyCheckpoint(checkpointMatch[1].trim());
      Object.assign(operation, {
        status: 'completed', stage: 'completed', checkpoint_path: verified.checkpoint_path,
        manifest_path: verified.manifest_path, artifact_count: verified.artifact_count,
        total_bytes: verified.total_bytes, verified: true, error_code: null,
      });
    } catch (error) {
      operation.status = 'failed'; operation.stage = 'failed';
      operation.error_code = String(error.message || 'backup_failed').slice(0, 100);
    } finally {
      activeBackupOperationId = null;
    }
  });
  return operation;
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY_BYTES) {
        reject(new Error('BODY_TOO_LARGE'));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}'));
      } catch (_) {
        reject(new Error('INVALID_JSON'));
      }
    });
    req.on('error', reject);
  });
}

function base64UrlDecode(value) {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padding = '='.repeat((4 - (normalized.length % 4)) % 4);
  return Buffer.from(normalized + padding, 'base64');
}

function verifyJwt(token) {
  const parts = token.split('.');

  if (parts.length !== 3) {
    throw new Error('Malformed token');
  }

  const [encodedHeader, encodedPayload, encodedSignature] = parts;

  const header = JSON.parse(
    base64UrlDecode(encodedHeader).toString('utf8'),
  );

  if (header.alg !== 'HS256') {
    throw new Error('Unexpected JWT algorithm');
  }

  const signingInput = `${encodedHeader}.${encodedPayload}`;

  const expected = crypto
    .createHmac('sha256', SECRET_KEY)
    .update(signingInput)
    .digest();

  const actual = base64UrlDecode(encodedSignature);

  if (
    actual.length !== expected.length ||
    !crypto.timingSafeEqual(actual, expected)
  ) {
    throw new Error('Invalid JWT signature');
  }

  const payload = JSON.parse(
    base64UrlDecode(encodedPayload).toString('utf8'),
  );

  const now = Math.floor(Date.now() / 1000);

  if (payload.nbf && Number(payload.nbf) > now) {
    throw new Error('Token not active');
  }

  if (payload.exp && Number(payload.exp) <= now) {
    throw new Error('Token expired');
  }

  if (payload.type !== 'access') {
    throw new Error('Invalid token type');
  }

  const role = String(payload.role || '').trim().toLowerCase();

  if (role !== 'administrator' && role !== 'admin') {
    throw new Error('Administrator role required');
  }

  return payload;
}

function authorize(req) {
  const header = String(req.headers.authorization || '');
  const match = /^Bearer\s+(.+)$/i.exec(header);

  if (!match) {
    throw new Error('Missing bearer token');
  }

  return verifyJwt(match[1]);
}

function runDocker(args) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      'docker',
      args,
      {
        cwd: PROJECT_DIR,
        windowsHide: true,
        shell: false,
      },
    );

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    child.on('error', reject);

    child.on('close', (code) => {
      if (code !== 0) {
        reject(
          new Error(
            `docker ${args.join(' ')} failed (${code}): ${stderr.trim()}`,
          ),
        );
        return;
      }

      resolve({
        stdout,
        stderr,
      });
    });
  });
}

async function getServices() {
  const result = await runDocker([
    'compose',
    'ps',
    '--format',
    'json',
  ]);

  const states = {};

  for (const service of CORE_SERVICES) {
    states[service] = false;
  }

  const lines = result.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  for (const line of lines) {
    let item;

    try {
      item = JSON.parse(line);
    } catch (_) {
      continue;
    }

    const service = String(item.Service || item.service || '');
    const state = String(item.State || item.state || '').toLowerCase();

    if (Object.prototype.hasOwnProperty.call(states, service)) {
      states[service] = state === 'running';
    }
  }

  return states;
}

async function statusPayload() {
  const services = await getServices();

  return {
    supervisor_online: true,
    system_running: CORE_SERVICES.every(
      (service) => services[service] === true,
    ),
    services,
  };
}

function sendJson(res, statusCode, payload) {
  const body = JSON.stringify(payload);

  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
  });

  res.end(body);
}

async function handle(req, res) {
  if (req.method === 'GET' && req.url === '/health') {
    sendJson(res, 200, {
      supervisor_online: true,
    });
    return;
  }

  const requestUrl = new URL(req.url, `http://${HOST}:${PORT}`);
  if (requestUrl.pathname.startsWith('/vision/')) {
    try {
      authorizeVision(req);
    } catch (_) {
      sendJson(res, 401, { detail: 'Unauthorized' });
      return;
    }
    try {
      if (req.method === 'GET' && requestUrl.pathname === '/vision/health') {
        sendJson(res, 200, visionQueue.health());
        return;
      }
      if (req.method === 'POST' && requestUrl.pathname === '/vision/jobs') {
        sendJson(res, 202, visionQueue.create(await readJsonBody(req)));
        return;
      }
      if (req.method === 'POST' && requestUrl.pathname === '/vision/resume') {
        sendJson(res, 202, visionQueue.resume());
        return;
      }
      const match = /^\/vision\/jobs\/([a-f0-9-]{36})(\/cancel)?$/i.exec(requestUrl.pathname);
      if (match && req.method === 'GET' && !match[2]) {
        const status = visionQueue.get(match[1]);
        sendJson(res, status ? 200 : 404, status || { detail: 'Not found' });
        return;
      }
      if (match && req.method === 'POST' && match[2]) {
        const status = visionQueue.cancel(match[1]);
        sendJson(res, status ? 202 : 404, status || { detail: 'Not found' });
        return;
      }
      sendJson(res, 404, { detail: 'Not found' });
      return;
    } catch (error) {
      const badRequest = ['BODY_TOO_LARGE', 'INVALID_JSON'].includes(error.message) || /^(INVALID|SOURCE_)/.test(error.message);
      sendJson(res, badRequest ? 422 : 500, { detail: badRequest ? 'Invalid Vision job request' : 'Vision supervisor failure' });
      return;
    }
  }

  if (requestUrl.pathname.startsWith('/backup/')) {
    try {
      authorizeBackup(req);
    } catch (_) {
      sendJson(res, 401, { code: 'unauthorized' });
      return;
    }
    try {
      if (req.method === 'POST' && requestUrl.pathname === '/backup/run') {
        sendJson(res, 202, startBackupOperation(await readJsonBody(req)));
        return;
      }
      const operationMatch = /^\/backup\/operations\/([a-f0-9-]{36})$/i.exec(requestUrl.pathname);
      if (req.method === 'GET' && operationMatch) {
        const operation = backupOperations.get(operationMatch[1]);
        sendJson(res, operation ? 200 : 404, operation || { code: 'backup_operation_not_found' });
        return;
      }
      if (req.method === 'POST' && requestUrl.pathname === '/backup/checkpoints') {
        const payload = await readJsonBody(req);
        if (!Array.isArray(payload.destinations)) throw new Error('backup_destinations_invalid');
        sendJson(res, 200, { items: await discoverCheckpoints(payload.destinations) });
        return;
      }
      sendJson(res, 404, { code: 'not_found' });
      return;
    } catch (error) {
      const code = String(error.message || 'backup_supervisor_failure').slice(0, 100);
      const invalid = code.includes('invalid') || code.includes('active_path') || code.includes('already_running');
      sendJson(res, invalid ? 409 : 500, { code });
      return;
    }
  }

  try {
    authorize(req);
  } catch (error) {
    sendJson(res, 401, {
      detail: 'Unauthorized',
    });
    return;
  }

  try {
    if (req.method === 'GET' && req.url === '/status') {
      sendJson(res, 200, await statusPayload());
      return;
    }

    if (req.method === 'POST' && req.url === '/start') {
      await runDocker([
        'compose',
        'up',
        '-d',
      ]);

      sendJson(res, 202, {
        status: 'accepted',
        action: 'start',
      });
      return;
    }

    if (req.method === 'POST' && req.url === '/restart') {
      await runDocker([
        'compose',
        'restart',
      ]);

      sendJson(res, 202, {
        status: 'accepted',
        action: 'restart',
      });
      return;
    }

    if (req.method === 'POST' && req.url === '/stop') {
      await runDocker([
        'compose',
        'stop',
      ]);

      sendJson(res, 202, {
        status: 'accepted',
        action: 'stop',
      });
      return;
    }

    sendJson(res, 404, {
      detail: 'Not found',
    });
  } catch (error) {
    sendJson(res, 500, {
      detail: 'Supervisor action failed',
    });
  }
}

const server = http.createServer((req, res) => {
  handle(req, res).catch(() => {
    sendJson(res, 500, {
      detail: 'Unhandled supervisor error',
    });
  });
});

server.listen(PORT, HOST, () => {
  process.stdout.write(
    `AI-Lab supervisor listening on http://${HOST}:${PORT}\n`,
  );
});

const cleanupTimer = setInterval(() => visionQueue.cleanup(), 60 * 60 * 1000);
cleanupTimer.unref();
