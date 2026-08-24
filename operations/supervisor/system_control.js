'use strict';

const CONTROLLED_WORKLOAD_SERVICES = Object.freeze([
  'qdrant',
  'ollama',
  'n8n',
  'open-webui',
]);

function controlledDockerArgs(command) {
  if (command === 'start') return ['compose', 'up', '-d'];
  if (command === 'start_workloads') {
    return ['compose', 'up', '-d', ...CONTROLLED_WORKLOAD_SERVICES];
  }
  if (command === 'stop') {
    return ['compose', 'stop', ...CONTROLLED_WORKLOAD_SERVICES];
  }
  throw new Error('system_control_command_invalid');
}

module.exports = { CONTROLLED_WORKLOAD_SERVICES, controlledDockerArgs };
