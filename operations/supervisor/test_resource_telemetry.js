'use strict';

const assert = require('assert');
const { resourceTelemetry } = require('./resource_telemetry');

const timestamp = new Date('2026-08-26T12:00:00.000Z');
const payload = resourceTelemetry(timestamp);

assert(Number.isSafeInteger(payload.physical_total_bytes));
assert(Number.isSafeInteger(payload.physical_available_bytes));
assert(payload.physical_total_bytes > 0);
assert(payload.physical_available_bytes >= 0);
assert(payload.physical_available_bytes <= payload.physical_total_bytes);
assert.strictEqual(payload.timestamp, timestamp.toISOString());
assert.deepStrictEqual(Object.keys(payload).sort(), [
  'physical_available_bytes',
  'physical_total_bytes',
  'timestamp',
]);

console.log('Supervisor resource telemetry tests passed.');
