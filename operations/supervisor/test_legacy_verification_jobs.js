'use strict';

const assert = require('assert');
const { LegacyVerificationJobs } = require('./legacy_verification_jobs');

async function waitFor(queue, jobId) {
  for (let index = 0; index < 100; index += 1) {
    const state = queue.get(jobId);
    if (['READY_TO_ADOPT', 'FAILED', 'CANCELLED'].includes(state.state)) return state;
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  throw new Error('fixture_timeout');
}

async function main() {
  const updates = [];
  const queue = new LegacyVerificationJobs({
    verify: async (root, checkpoint, update) => {
      assert.strictEqual(root, 'D:\\backups');
      assert.strictEqual(checkpoint, 'D:\\backups\\fixture');
      update({ state: 'VERIFYING_MANIFEST' });
      update({ state: 'VERIFYING_FILES', files_total: 2 });
      update({
        state: 'VERIFYING_CHECKSUMS',
        files_checked: 1,
        files_total: 2,
        bytes_checked: 5,
        bytes_total: 10,
      });
      updates.push('verified');
      return { verified: true, manifest_sha256: 'a'.repeat(64) };
    },
  });
  const jobId = '11111111-1111-4111-8111-111111111111';
  const created = queue.create({
    job_id: jobId,
    destination_root: 'D:\\backups',
    checkpoint_path: 'D:\\backups\\fixture',
  });
  assert.strictEqual(created.state, 'QUEUED');
  const duplicate = queue.create({
    job_id: '22222222-2222-4222-8222-222222222222',
    destination_root: 'D:\\backups',
    checkpoint_path: 'D:\\backups\\fixture',
  });
  assert.strictEqual(duplicate.job_id, jobId);
  const completed = await waitFor(queue, jobId);
  assert.strictEqual(completed.state, 'READY_TO_ADOPT');
  assert.strictEqual(completed.files_checked, 1);
  assert.strictEqual(queue.result(jobId).verified, true);
  assert.deepStrictEqual(updates, ['verified']);

  const failedQueue = new LegacyVerificationJobs({
    verify: async () => { throw new Error('backup_artifact_hash_mismatch'); },
  });
  const failedId = '33333333-3333-4333-8333-333333333333';
  failedQueue.create({
    job_id: failedId,
    destination_root: 'D:\\backups',
    checkpoint_path: 'D:\\backups\\failed',
  });
  const failed = await waitFor(failedQueue, failedId);
  assert.strictEqual(failed.state, 'FAILED');
  assert.strictEqual(failed.error_code, 'backup_artifact_hash_mismatch');
  assert.strictEqual(failedQueue.result(failedId), null);

  let releaseCancelled;
  const cancelledQueue = new LegacyVerificationJobs({
    verify: async (_root, _checkpoint, update) => {
      update({ state: 'VERIFYING_CHECKSUMS' });
      await new Promise((resolve) => { releaseCancelled = resolve; });
      update({ bytes_checked: 1 });
      return { verified: true };
    },
  });
  const cancelledId = '44444444-4444-4444-8444-444444444444';
  cancelledQueue.create({
    job_id: cancelledId,
    destination_root: 'D:\\backups',
    checkpoint_path: 'D:\\backups\\cancelled',
  });
  await new Promise((resolve) => setTimeout(resolve, 5));
  cancelledQueue.cancel(cancelledId);
  releaseCancelled();
  const cancelled = await waitFor(cancelledQueue, cancelledId);
  assert.strictEqual(cancelled.state, 'CANCELLED');
  process.stdout.write('LEGACY_VERIFICATION_JOB_TESTS=PASS\n');
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
