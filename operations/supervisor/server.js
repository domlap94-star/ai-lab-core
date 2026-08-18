'use strict';

const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { VisionQueue, MAX_BODY_BYTES } = require('./vision_queue');

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
