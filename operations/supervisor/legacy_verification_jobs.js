'use strict';

const TERMINAL = new Set(['READY_TO_ADOPT', 'FAILED', 'CANCELLED']);

class LegacyVerificationJobs {
  constructor({ verify, maxJobs = 100 }) {
    this.verify = verify;
    this.maxJobs = maxJobs;
    this.jobs = new Map();
    this.activeByCheckpoint = new Map();
  }

  create(payload) {
    const jobId = String(payload.job_id || '');
    const root = String(payload.destination_root || '');
    const checkpoint = String(payload.checkpoint_path || '');
    if (!/^[a-f0-9-]{36}$/i.test(jobId) || !root || !checkpoint) {
      throw new Error('legacy_verification_request_invalid');
    }
    const key = checkpoint.toLowerCase();
    const existingId = this.activeByCheckpoint.get(key);
    if (existingId) {
      const existing = this.jobs.get(existingId);
      if (existing && !TERMINAL.has(existing.state)) return this.public(existing);
      this.activeByCheckpoint.delete(key);
    }
    if (this.jobs.has(jobId)) return this.public(this.jobs.get(jobId));
    while (this.jobs.size >= this.maxJobs) {
      const removable = [...this.jobs.values()].find((item) => TERMINAL.has(item.state));
      if (!removable) throw new Error('legacy_verification_capacity_reached');
      this.jobs.delete(removable.job_id);
    }
    const now = new Date().toISOString();
    const job = {
      job_id: jobId,
      destination_root: root,
      checkpoint_path: checkpoint,
      state: 'QUEUED',
      files_checked: 0,
      files_total: null,
      bytes_checked: 0,
      bytes_total: null,
      error_code: null,
      retryable: false,
      created_at: now,
      updated_at: now,
      cancel_requested: false,
      result: null,
    };
    this.jobs.set(jobId, job);
    this.activeByCheckpoint.set(key, jobId);
    setImmediate(() => this.run(job));
    return this.public(job);
  }

  async run(job) {
    try {
      const update = (progress) => {
        if (job.cancel_requested) throw new Error('legacy_verification_cancelled');
        Object.assign(job, progress, { updated_at: new Date().toISOString() });
      };
      const result = await this.verify(
        job.destination_root,
        job.checkpoint_path,
        update,
      );
      if (job.cancel_requested) throw new Error('legacy_verification_cancelled');
      job.result = result;
      job.state = 'READY_TO_ADOPT';
      job.updated_at = new Date().toISOString();
    } catch (error) {
      const code = String(error.message || 'legacy_verification_failed').slice(0, 100);
      job.state = code === 'legacy_verification_cancelled' ? 'CANCELLED' : 'FAILED';
      job.error_code = code;
      job.retryable = [
        'backup_destination_unavailable',
        'backup_supervisor_unavailable',
        'legacy_verification_interrupted',
      ].includes(code);
      job.updated_at = new Date().toISOString();
    } finally {
      this.activeByCheckpoint.delete(job.checkpoint_path.toLowerCase());
    }
  }

  get(jobId) {
    const job = this.jobs.get(String(jobId));
    return job ? this.public(job) : null;
  }

  result(jobId) {
    const job = this.jobs.get(String(jobId));
    if (!job || job.state !== 'READY_TO_ADOPT') return null;
    return { ...job.result };
  }

  cancel(jobId) {
    const job = this.jobs.get(String(jobId));
    if (!job) return null;
    if (!TERMINAL.has(job.state)) {
      job.cancel_requested = true;
      job.updated_at = new Date().toISOString();
    }
    return this.public(job);
  }

  public(job) {
    return {
      job_id: job.job_id,
      state: job.state,
      files_checked: job.files_checked,
      files_total: job.files_total,
      bytes_checked: job.bytes_checked,
      bytes_total: job.bytes_total,
      error_code: job.error_code,
      retryable: job.retryable,
      created_at: job.created_at,
      updated_at: job.updated_at,
    };
  }
}

module.exports = { LegacyVerificationJobs };
