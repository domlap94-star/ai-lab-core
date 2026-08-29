'use strict';

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');

function normalizeDestination(value, projectDir) {
  const raw = String(value || '').trim().replace(/\//g, '\\');
  if (/^\\\\[?.]\\/.test(raw) || raw.split('\\').includes('..')) throw new Error('backup_destination_invalid');
  const drivePath = /^[A-Za-z]:\\/.test(raw);
  const uncPath = /^\\\\[^\\]+\\[^\\]+\\/.test(raw);
  if (!drivePath && !uncPath) throw new Error('backup_destination_invalid');
  const resolved = path.win32.normalize(raw).replace(/[\\]+$/, '');
  const parsed = path.win32.parse(resolved);
  if (!parsed.root || resolved.toLowerCase() === parsed.root.replace(/[\\]+$/, '').toLowerCase()) {
    throw new Error('backup_destination_root_forbidden');
  }
  const repo = path.win32.normalize(projectDir).replace(/[\\]+$/, '').toLowerCase();
  const lower = resolved.toLowerCase();
  if (lower === repo || lower.startsWith(`${repo}\\`)) throw new Error('backup_destination_active_path');
  return resolved;
}

function sha256File(filePath) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

function destinationPreflight(value, projectDir) {
  const destination = normalizeDestination(value, projectDir);
  if (!fs.existsSync(destination) || !fs.statSync(destination).isDirectory()) throw new Error('backup_destination_unavailable');
  const real = fs.realpathSync.native(destination);
  const probe = path.join(real, `.next-stabil-write-probe-${crypto.randomUUID()}`);
  try {
    fs.writeFileSync(probe, '', { flag: 'wx' });
  } catch (_) {
    throw new Error('backup_destination_not_writable');
  } finally {
    try { if (fs.existsSync(probe)) fs.unlinkSync(probe); } catch (_) { /* bounded probe cleanup */ }
  }
  const stats = fs.statfsSync(real);
  const identity = path.win32.parse(destination).root.toUpperCase();
  return {
    normalized_destination: destination,
    available: true,
    writable: true,
    total_bytes: Number(stats.blocks) * Number(stats.bsize),
    free_bytes: Number(stats.bavail) * Number(stats.bsize),
    destination_identity: identity,
    destination_filesystem: null,
    checked_at: new Date().toISOString(),
  };
}

function destinationMetadata(value, projectDir) {
  const destination = normalizeDestination(value, projectDir);
  if (!fs.existsSync(destination) || !fs.statSync(destination).isDirectory()) {
    return {
      normalized_destination: destination,
      available: false,
      writable: false,
      total_bytes: 0,
      free_bytes: 0,
      path_type: destination.startsWith('\\\\') ? 'network_path' : 'local_path',
    };
  }
  const real = fs.realpathSync.native(destination);
  if (fs.lstatSync(destination).isSymbolicLink()) throw new Error('backup_destination_reparse_forbidden');
  let writable = true;
  try { fs.accessSync(real, fs.constants.R_OK | fs.constants.W_OK); } catch (_) { writable = false; }
  const stats = fs.statfsSync(real);
  return {
    normalized_destination: destination,
    available: true,
    writable,
    total_bytes: Number(stats.blocks) * Number(stats.bsize),
    free_bytes: Number(stats.bavail) * Number(stats.bsize),
    destination_identity: path.win32.parse(destination).root.toUpperCase(),
    destination_filesystem: null,
    path_type: destination.startsWith('\\\\') ? 'network_path' : 'local_path',
  };
}

function browseDestination(value, relativePath, projectDir) {
  const root = normalizeDestination(value, projectDir);
  const relative = String(relativePath || '').trim().replace(/\//g, '\\');
  if (path.win32.isAbsolute(relative) || relative.split('\\').includes('..')) {
    throw new Error('backup_destination_relative_path_invalid');
  }
  const rootReal = fs.realpathSync.native(root);
  const target = path.win32.resolve(rootReal, relative || '.');
  if (target.toLowerCase() !== rootReal.toLowerCase()
      && !target.toLowerCase().startsWith(`${rootReal.toLowerCase()}\\`)) {
    throw new Error('backup_destination_browse_escape');
  }
  const targetReal = fs.realpathSync.native(target);
  if (targetReal.toLowerCase() !== rootReal.toLowerCase()
      && !targetReal.toLowerCase().startsWith(`${rootReal.toLowerCase()}\\`)) {
    throw new Error('backup_destination_reparse_escape');
  }
  if (fs.lstatSync(target).isSymbolicLink()) throw new Error('backup_destination_reparse_forbidden');
  const directories = fs.readdirSync(target, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.isSymbolicLink())
    .slice(0, 100)
    .map((entry) => ({
      name: entry.name,
      relative_path: path.win32.join(relative, entry.name),
    }));
  return { relative_path: relative, directories };
}

function listedFiles(root) {
  const output = [];
  function walk(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name);
      const stat = fs.lstatSync(absolute);
      if (stat.isSymbolicLink()) throw new Error('managed_backup_reparse_forbidden');
      if (entry.isDirectory()) walk(absolute);
      else if (entry.isFile()) output.push(path.relative(root, absolute).replace(/\\/g, '/'));
      else throw new Error('managed_backup_file_type_forbidden');
    }
  }
  walk(root);
  return output.sort();
}

function deleteManagedBackup(payload, projectDir, activeBackupOperationId = null) {
  if (activeBackupOperationId) throw new Error('managed_backup_active');
  const root = normalizeDestination(payload.destination_root, projectDir);
  const checkpoint = path.win32.normalize(String(payload.checkpoint_path || '')).replace(/[\\]+$/, '');
  const manifestPath = path.win32.normalize(String(payload.manifest_path || ''));
  const rootPrefix = `${root.toLowerCase()}\\`;
  if (!checkpoint.toLowerCase().startsWith(rootPrefix) || checkpoint.toLowerCase() === root.toLowerCase()) {
    throw new Error('managed_backup_wrong_root');
  }
  if (manifestPath.toLowerCase() !== path.win32.join(checkpoint, 'backup-manifest.json').toLowerCase()) {
    throw new Error('managed_backup_manifest_path_invalid');
  }
  if (!fs.existsSync(root) || !fs.existsSync(checkpoint) || !fs.existsSync(manifestPath)) throw new Error('managed_backup_missing');
  const rootReal = fs.realpathSync.native(root);
  const checkpointReal = fs.realpathSync.native(checkpoint);
  if (!checkpointReal.toLowerCase().startsWith(`${rootReal.toLowerCase()}\\`)) throw new Error('managed_backup_reparse_escape');
  if (fs.lstatSync(checkpoint).isSymbolicLink()) throw new Error('managed_backup_reparse_forbidden');
  if (sha256File(manifestPath).toLowerCase() !== String(payload.manifest_sha256 || '').toLowerCase()) {
    throw new Error('managed_backup_manifest_hash_mismatch');
  }
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8').replace(/^\uFEFF/, ''));
  if (!['NEXT_STABIL_BACKUP_V1', 'NEXT_STABIL_BACKUP_V2'].includes(manifest.schema_version) || !Array.isArray(manifest.artifacts)) {
    throw new Error('managed_backup_manifest_invalid');
  }
  const allowed = new Set(['backup-manifest.json']);
  let actualBytes = fs.statSync(manifestPath).size;
  for (const artifact of manifest.artifacts) {
    const relative = String(artifact.file || '').replace(/\\/g, '/');
    if (!relative || path.posix.isAbsolute(relative) || relative.split('/').includes('..')) throw new Error('managed_backup_artifact_path_invalid');
    const target = path.join(checkpointReal, ...relative.split('/'));
    const targetReal = fs.realpathSync.native(target);
    if (!targetReal.toLowerCase().startsWith(`${checkpointReal.toLowerCase()}\\`)) throw new Error('managed_backup_reparse_escape');
    const stat = fs.statSync(targetReal);
    if (!stat.isFile() || stat.size !== Number(artifact.bytes)) throw new Error('managed_backup_artifact_invalid');
    if (sha256File(targetReal).toLowerCase() !== String(artifact.sha256 || '').toLowerCase()) throw new Error('managed_backup_artifact_hash_mismatch');
    allowed.add(relative);
    actualBytes += stat.size;
  }
  const actual = listedFiles(checkpointReal);
  if (actual.some((name) => !allowed.has(name))) throw new Error('managed_backup_unmanaged_file_present');
  fs.rmSync(checkpointReal, { recursive: true, force: false });
  if (fs.existsSync(checkpointReal)) throw new Error('managed_backup_delete_unverified');
  return { status: 'deleted', actual_reclaimed_bytes: actualBytes };
}

module.exports = {
  normalizeDestination,
  destinationPreflight,
  destinationMetadata,
  browseDestination,
  deleteManagedBackup,
  listedFiles,
  sha256File,
};
