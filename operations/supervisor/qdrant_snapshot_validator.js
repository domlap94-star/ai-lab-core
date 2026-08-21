'use strict';

const { spawn } = require('child_process');
const path = require('path');

const MAX_LIST_BYTES = 4 * 1024 * 1024;
const MAX_METADATA_BYTES = 64 * 1024;
const TAR = process.platform === 'win32' && process.env.SystemRoot
  ? path.join(process.env.SystemRoot, 'System32', 'tar.exe')
  : 'tar';

function runTar(args, maxBytes) {
  return new Promise((resolve, reject) => {
    const child = spawn(TAR, args, { windowsHide: true, shell: false });
    const chunks = [];
    const errors = [];
    let bytes = 0;
    child.stdout.on('data', (chunk) => {
      bytes += chunk.length;
      if (bytes > maxBytes) {
        child.kill();
        reject(new Error('qdrant_snapshot_metadata_too_large'));
        return;
      }
      chunks.push(chunk);
    });
    child.stderr.on('data', (chunk) => errors.push(chunk));
    child.on('error', reject);
    child.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(`qdrant_snapshot_archive_invalid:${Buffer.concat(errors).toString('utf8').slice(0, 200)}`));
        return;
      }
      resolve(Buffer.concat(chunks));
    });
  });
}

function normalizeEntry(value) {
  return String(value || '').replace(/\\/g, '/').replace(/^\.\//, '');
}

function isSafeEntry(entry) {
  return entry && !entry.startsWith('/') && !/^[A-Za-z]:/.test(entry) && !/(^|\/)\.\.(\/|$)/.test(entry);
}

async function validateQdrantSnapshot(snapshotPath) {
  try {
    const listed = await runTar(['-tf', snapshotPath], MAX_LIST_BYTES);
    const entries = listed.toString('utf8').split(/\r?\n/).map(normalizeEntry).filter(Boolean);
    if (!entries.length || entries.some((entry) => !isSafeEntry(entry))) {
      return { valid: false, error_code: 'qdrant_snapshot_invalid', reason: 'archive_entries_invalid' };
    }
    const hasConfig = entries.includes('config.json');
    const hasVersion = entries.includes('version.info');
    const hasShardMetadata = entries.some((entry) => /^\d+\/shard_config\.json$/.test(entry));
    if (!hasConfig || !hasVersion || !hasShardMetadata) {
      return { valid: false, error_code: 'qdrant_snapshot_invalid', reason: 'collection_metadata_missing' };
    }
    const firstIndexes = entries.filter((entry) => /^\d+\/wal\/first-index$/.test(entry));
    for (const entry of firstIndexes) {
      const bytes = await runTar(['-xOf', snapshotPath, entry], MAX_METADATA_BYTES);
      if (!bytes.length || bytes.every((value) => value === 0)) {
        return { valid: false, error_code: 'qdrant_snapshot_invalid', reason: 'wal_first_index_empty_or_nul' };
      }
      let metadata;
      try { metadata = JSON.parse(bytes.toString('utf8')); } catch (_) {
        return { valid: false, error_code: 'qdrant_snapshot_invalid', reason: 'wal_first_index_invalid_json' };
      }
      if (!Number.isInteger(metadata.ack_index) || metadata.ack_index < 0) {
        return { valid: false, error_code: 'qdrant_snapshot_invalid', reason: 'wal_first_index_invalid_value' };
      }
    }
    return {
      valid: true,
      error_code: null,
      reason: null,
      snapshot_structurally_valid: true,
      first_index_entries: firstIndexes.length,
    };
  } catch (error) {
    return { valid: false, error_code: 'qdrant_snapshot_invalid', reason: String(error.message || 'archive_invalid').split(':')[0] };
  }
}

if (require.main === module) {
  const snapshotPath = process.argv[2];
  if (!snapshotPath) {
    process.stderr.write('snapshot path required\n');
    process.exitCode = 2;
  } else {
    validateQdrantSnapshot(snapshotPath).then((result) => {
      process.stdout.write(`${JSON.stringify(result)}\n`);
      // A structurally invalid artifact is a successful validation outcome,
      // not a validator process failure. Callers inspect `valid` and persist a
      // fail-closed eligibility state without aborting the whole backup.
      process.exitCode = 0;
    }).catch((error) => {
      process.stderr.write(`${error.message}\n`);
      process.exitCode = 2;
    });
  }
}

module.exports = { validateQdrantSnapshot };
