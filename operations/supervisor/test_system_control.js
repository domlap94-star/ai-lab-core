'use strict';

const assert = require('assert');
const {
  CONTROLLED_WORKLOAD_SERVICES,
  controlledDockerArgs,
} = require('./system_control');

assert.deepStrictEqual(CONTROLLED_WORKLOAD_SERVICES, [
  'qdrant', 'ollama', 'n8n', 'open-webui',
]);
assert.deepStrictEqual(controlledDockerArgs('start'), ['compose', 'up', '-d']);
assert.deepStrictEqual(controlledDockerArgs('start_workloads'), [
  'compose', 'up', '-d', 'qdrant', 'ollama', 'n8n', 'open-webui',
]);
assert.deepStrictEqual(controlledDockerArgs('stop'), [
  'compose', 'stop', 'qdrant', 'ollama', 'n8n', 'open-webui',
]);
assert.throws(() => controlledDockerArgs('shell'), /system_control_command_invalid/);
assert(!CONTROLLED_WORKLOAD_SERVICES.includes('backend'));
assert(!CONTROLLED_WORKLOAD_SERVICES.includes('postgres'));
process.stdout.write('SUPERVISOR_SYSTEM_CONTROL_BOUNDARY=PASS\n');
