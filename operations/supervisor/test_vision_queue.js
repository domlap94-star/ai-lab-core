'use strict';

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { EventEmitter } = require('events');
const { VisionQueue } = require('./vision_queue');

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'vision-queue-'));
const requestKey = 'a'.repeat(64);
const incoming = path.join(root, 'incoming', requestKey);
fs.mkdirSync(incoming, { recursive: true });
const input = path.join(incoming, 'S1.png');
fs.writeFileSync(input, 'synthetic');
const sha256 = crypto.createHash('sha256').update('synthetic').digest('hex');
const children = [];
const queue = new VisionQueue({ spoolRoot: root, workerScript: 'worker.js', workerRoot: root, spawnWorker: () => {
  const child = new EventEmitter(); child.kill = () => child.emit('close', 2, 'cancelled'); children.push(child); return child;
} });
const request = { request_key: requestKey, sources: [{ source_ref: 'S1', document_id: 1, page_number: null, asset_id: null, sha256, incoming_relative_path: `incoming/${requestKey}/S1.png` }] };
const created = queue.create(request);
assert.strictEqual(queue.create(request).job_id, created.job_id);
assert.strictEqual(queue.health().status, 'BUSY');
children[0].visionOutput = '';
children[0].emit('close', 0);
setImmediate(() => {
  assert.strictEqual(queue.get(created.job_id).state, 'COMPLETE');
  assert.strictEqual(queue.get('unknown'), null);
  queue._set(created.job_id, { state: 'QUEUED', next_retry_at: new Date().toISOString() });
  const cancelled = queue.cancel(created.job_id);
  assert.strictEqual(cancelled.state, 'CANCELLED');
  assert.strictEqual(cancelled.next_retry_at, null);
  assert.throws(() => queue.create({ request_key: 'b'.repeat(64), sources: [{ ...request.sources[0], incoming_relative_path: '../outside.png' }] }), /PATH/);
  assert.throws(() => queue.create({ ...request, request_key: 'c'.repeat(64), command: 'whoami' }), /FIELD/);
  assert.throws(() => queue.create({ ...request, request_key: 'd'.repeat(64), url: 'https://example.invalid/x.png' }), /FIELD/);
  assert.throws(() => queue.create({ request_key: 'e'.repeat(64), sources: [{ ...request.sources[0], url: 'https://example.invalid/x.png' }] }), /FIELD/);
  fs.rmSync(root, { recursive: true, force: true });
  process.stdout.write('VISION SUPERVISOR QUEUE TESTS: OK\n');
});
