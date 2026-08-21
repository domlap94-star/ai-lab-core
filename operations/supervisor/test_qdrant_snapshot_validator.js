'use strict';

const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const { validateQdrantSnapshot } = require('./qdrant_snapshot_validator');
const TAR = process.platform === 'win32' && process.env.SystemRoot
  ? path.join(process.env.SystemRoot, 'System32', 'tar.exe')
  : 'tar';

function makeSnapshot(root, name, firstIndex) {
  const source = path.join(root, `${name}-source`);
  fs.mkdirSync(path.join(source, '0', 'wal'), { recursive: true });
  fs.writeFileSync(path.join(source, 'config.json'), '{}');
  fs.writeFileSync(path.join(source, 'version.info'), '1.18.3');
  fs.writeFileSync(path.join(source, '0', 'shard_config.json'), '{}');
  if (firstIndex !== undefined) fs.writeFileSync(path.join(source, '0', 'wal', 'first-index'), firstIndex);
  const snapshot = path.join(root, `${name}.snapshot`);
  const result = spawnSync(TAR, ['-cf', snapshot, '-C', source, '.'], { windowsHide: true });
  assert.ifError(result.error);
  assert.strictEqual(result.status, 0, result.stderr.toString());
  return snapshot;
}

function makeMissingMetadataSnapshot(root) {
  const source = path.join(root, 'missing-source');
  fs.mkdirSync(source, { recursive: true });
  fs.writeFileSync(path.join(source, 'version.info'), '1.18.3');
  const snapshot = path.join(root, 'missing.snapshot');
  const result = spawnSync(TAR, ['-cf', snapshot, '-C', source, '.'], { windowsHide: true });
  assert.ifError(result.error);
  assert.strictEqual(result.status, 0, result.stderr.toString());
  return snapshot;
}

(async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'next-qdrant-validator-'));
  try {
    const healthy = makeSnapshot(root, 'healthy', Buffer.from('{"ack_index":5}'));
    const noIndex = makeSnapshot(root, 'healthy-no-index', undefined);
    const nul = makeSnapshot(root, 'nul', Buffer.alloc(15));
    const missing = makeMissingMetadataSnapshot(root);
    const malformed = path.join(root, 'malformed.snapshot');
    fs.writeFileSync(malformed, 'not a tar archive');

    assert.strictEqual((await validateQdrantSnapshot(healthy)).valid, true);
    assert.strictEqual((await validateQdrantSnapshot(noIndex)).valid, true);
    assert.deepStrictEqual(
      { valid: (await validateQdrantSnapshot(nul)).valid, reason: (await validateQdrantSnapshot(nul)).reason },
      { valid: false, reason: 'wal_first_index_empty_or_nul' },
    );
    assert.strictEqual((await validateQdrantSnapshot(malformed)).valid, false);
    assert.strictEqual((await validateQdrantSnapshot(missing)).reason, 'collection_metadata_missing');
    process.stdout.write('QDRANT_SNAPSHOT_VALIDATOR_TESTS=PASS\n');
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
})().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exitCode = 1;
});
