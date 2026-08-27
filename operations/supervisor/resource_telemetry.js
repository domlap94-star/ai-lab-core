'use strict';

const os = require('os');

function resourceTelemetry(now = new Date()) {
  const physicalTotalBytes = Number(os.totalmem());
  const physicalAvailableBytes = Number(os.freemem());
  if (
    !Number.isSafeInteger(physicalTotalBytes)
    || !Number.isSafeInteger(physicalAvailableBytes)
    || physicalTotalBytes <= 0
    || physicalAvailableBytes < 0
    || physicalAvailableBytes > physicalTotalBytes
  ) {
    throw new Error('RESOURCE_TELEMETRY_INVALID');
  }
  return {
    physical_total_bytes: physicalTotalBytes,
    physical_available_bytes: physicalAvailableBytes,
    timestamp: now.toISOString(),
  };
}

module.exports = { resourceTelemetry };
