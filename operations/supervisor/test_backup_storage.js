'use strict';

const assert = require('assert');
const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const {
  normalizeDestination,
  destinationPreflight,
  destinationMetadata,
  browseDestination,
  deleteManagedBackup,
  sha256File,
} = require('./backup_storage');

const testVolumeOverride = { allowSystemOrDataVolumeForTest: true };

function artifact(root, name, marker) {
  const checkpoint = path.join(root, name);
  fs.mkdirSync(checkpoint, { recursive: true });
  const dataPath = path.join(checkpoint, 'postgres.dump');
  fs.writeFileSync(dataPath, marker);
  const manifest = {
    schema_version: 'NEXT_STABIL_BACKUP_V2',
    artifacts: [{ file: 'postgres.dump', bytes: fs.statSync(dataPath).size, sha256: sha256File(dataPath) }],
  };
  const manifestPath = path.join(checkpoint, 'backup-manifest.json');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest));
  return { checkpoint, manifestPath, manifestHash: sha256File(manifestPath) };
}

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'next-stabil-retention-'));
const project = path.join(root, 'synthetic-project');
const backups = path.join(root, 'managed-root');
fs.mkdirSync(project); fs.mkdirSync(backups);
try {
  assert.throws(() => normalizeDestination('C:\\backups', project), /system_or_data_volume_forbidden/);
  assert.throws(() => normalizeDestination('D:\\backups', project), /system_or_data_volume_forbidden/);
  assert.strictEqual(normalizeDestination('F:\\backups', project), 'F:\\backups');
  const preflight = destinationPreflight(backups, project, testVolumeOverride);
  assert(preflight.available && preflight.writable && preflight.free_bytes > 0);
  const metadata = destinationMetadata(backups, project, testVolumeOverride);
  assert(metadata.available && metadata.writable && metadata.total_bytes > 0);
  fs.mkdirSync(path.join(backups, 'child'));
  const browsing = browseDestination(backups, '', project, testVolumeOverride);
  assert(browsing.directories.some((item) => item.name === 'child'));
  assert.throws(() => browseDestination(backups, '..', project, testVolumeOverride), /relative_path_invalid/);

  const wrong = artifact(root, 'wrong-root-backup', 'wrong');
  assert.throws(() => deleteManagedBackup({ checkpoint_path: wrong.checkpoint, destination_root: backups, manifest_path: wrong.manifestPath, manifest_sha256: wrong.manifestHash }, project, null, testVolumeOverride), /wrong_root/);

  const unmanaged = artifact(backups, 'unmanaged-fixture', 'unmanaged');
  fs.writeFileSync(path.join(unmanaged.checkpoint, 'photo.jpg'), 'must-survive');
  assert.throws(() => deleteManagedBackup({ checkpoint_path: unmanaged.checkpoint, destination_root: backups, manifest_path: unmanaged.manifestPath, manifest_sha256: unmanaged.manifestHash }, project, null, testVolumeOverride), /unmanaged_file/);
  assert(fs.existsSync(path.join(unmanaged.checkpoint, 'photo.jpg')));

  const active = artifact(backups, 'active-fixture', 'active');
  assert.throws(() => deleteManagedBackup({ checkpoint_path: active.checkpoint, destination_root: backups, manifest_path: active.manifestPath, manifest_sha256: active.manifestHash }, project, 'active-operation', testVolumeOverride), /active/);

  const escapeTarget = artifact(root, 'escape-target', 'escape');
  const junction = path.join(backups, 'junction-fixture');
  const junctionResult = spawnSync('cmd.exe', ['/d', '/c', 'mklink', '/J', junction, escapeTarget.checkpoint], { windowsHide: true });
  if (junctionResult.status === 0) {
    assert.throws(() => browseDestination(backups, 'junction-fixture', project, testVolumeOverride), /reparse/);
    assert.throws(() => deleteManagedBackup({ checkpoint_path: junction, destination_root: backups, manifest_path: path.join(junction, 'backup-manifest.json'), manifest_sha256: escapeTarget.manifestHash }, project, null, testVolumeOverride), /reparse/);
  }

  const valid = artifact(backups, 'valid-fixture', 'valid');
  const result = deleteManagedBackup({ checkpoint_path: valid.checkpoint, destination_root: backups, manifest_path: valid.manifestPath, manifest_sha256: valid.manifestHash }, project, null, testVolumeOverride);
  assert(result.actual_reclaimed_bytes > 0 && !fs.existsSync(valid.checkpoint));
  console.log('BACKUP_STORAGE_ISOLATED_TESTS=PASS');
} finally {
  fs.rmSync(root, { recursive: true, force: true });
}
