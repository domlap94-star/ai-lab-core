'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');

const HOST = '127.0.0.1';
const PORT = Number(process.env.AI_LAB_GATEWAY_PORT || '8788');

const REPO_ROOT = 'C:\\ai-lab-core';
const WEB_ROOT = path.join(REPO_ROOT, 'frontend', 'build', 'web');
const RELEASE_ROOT = path.join(REPO_ROOT, 'release-channel');

const BACKEND = {
  hostname: '127.0.0.1',
  port: 8000,
};

const SUPERVISOR = {
  hostname: '127.0.0.1',
  port: 8787,
};

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.wasm': 'application/wasm',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.apk': 'application/vnd.android.package-archive',
  '.exe': 'application/vnd.microsoft.portable-executable',
  '.zip': 'application/zip',
};

function sendJson(res, statusCode, payload) {
  const body = JSON.stringify(payload);

  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
  });

  res.end(body);
}

function proxy(req, res, target, rewrittenPath) {
  const headers = { ...req.headers };
  headers.host = `${target.hostname}:${target.port}`;

  const upstream = http.request(
    {
      hostname: target.hostname,
      port: target.port,
      method: req.method,
      path: rewrittenPath,
      headers,
    },
    (upstreamRes) => {
      res.writeHead(upstreamRes.statusCode || 502, upstreamRes.headers);
      upstreamRes.pipe(res);
    },
  );

  upstream.on('error', () => {
    if (!res.headersSent) {
      sendJson(res, 502, { detail: 'Upstream unavailable' });
    } else {
      res.end();
    }
  });

  req.pipe(upstream);
}

function safeJoin(root, requestPath) {
  const relative = requestPath.replace(/^\/+/, '');
  const resolved = path.resolve(root, relative);
  const normalizedRoot = path.resolve(root);

  if (
    resolved !== normalizedRoot &&
    !resolved.startsWith(normalizedRoot + path.sep)
  ) {
    return null;
  }

  return resolved;
}

function serveFile(req, res, filePath, noStore = false) {
  fs.stat(filePath, (statError, stat) => {
    if (statError || !stat.isFile()) {
      sendJson(res, 404, { detail: 'Not found' });
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const headers = {
      'Content-Type': MIME[ext] || 'application/octet-stream',
      'Content-Length': stat.size,
      'Cache-Control': noStore
        ? 'no-store'
        : ext === '.html'
          ? 'no-cache'
          : 'public, max-age=3600',
    };

    res.writeHead(200, headers);

    if (req.method === 'HEAD') {
      res.end();
      return;
    }

    fs.createReadStream(filePath).pipe(res);
  });
}

function serveUpdates(req, res, pathname) {
  const relative = pathname.replace(/^\/updates\/?/, '');
  const filePath = safeJoin(RELEASE_ROOT, relative);

  if (!filePath) {
    sendJson(res, 400, { detail: 'Invalid path' });
    return;
  }

  const noStore = path.basename(filePath).toLowerCase() === 'manifest.json';
  serveFile(req, res, filePath, noStore);
}

function serveWeb(req, res, pathname) {
  let requested = pathname === '/' ? '/index.html' : pathname;
  let filePath = safeJoin(WEB_ROOT, requested);

  if (!filePath) {
    sendJson(res, 400, { detail: 'Invalid path' });
    return;
  }

  fs.stat(filePath, (error, stat) => {
    if (!error && stat.isFile()) {
      serveFile(req, res, filePath);
      return;
    }

    // Flutter SPA fallback.
    serveFile(req, res, path.join(WEB_ROOT, 'index.html'), true);
  });
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${HOST}:${PORT}`);
  const pathname = url.pathname;
  const withQuery = `${pathname}${url.search}`;

  if (pathname === '/gateway-health') {
    sendJson(res, 200, {
      gateway_online: true,
      web_root_exists: fs.existsSync(
        path.join(WEB_ROOT, 'index.html'),
      ),
    });
    return;
  }

  if (
    pathname === '/version' ||
    pathname === '/health' ||
    pathname.startsWith('/api/')
  ) {
    proxy(req, res, BACKEND, withQuery);
    return;
  }

  if (pathname === '/control' || pathname.startsWith('/control/')) {
    const strippedPath = pathname.replace(/^\/control/, '') || '/';
    proxy(
      req,
      res,
      SUPERVISOR,
      `${strippedPath}${url.search}`,
    );
    return;
  }

  if (pathname === '/updates' || pathname.startsWith('/updates/')) {
    serveUpdates(req, res, pathname);
    return;
  }

  if (req.method !== 'GET' && req.method !== 'HEAD') {
    sendJson(res, 405, { detail: 'Method not allowed' });
    return;
  }

  serveWeb(req, res, pathname);
});

server.listen(PORT, HOST, () => {
  process.stdout.write(
    `AI-Lab gateway listening on http://${HOST}:${PORT}\n`,
  );
});