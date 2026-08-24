'use strict';

const path = require('path');
const { spawn } = require('child_process');

const MAX_SCHEDULES = 10;
const SAFE_CADENCES = new Set(['daily', 'weekly', 'monthly']);

function normalizeSchedule(input) {
  const id = Number(input && input.id);
  const enabled = input && input.enabled;
  const cadence = String((input && input.cadence) || '');
  const localTime = String((input && input.local_time) || '');
  const weekday = input && input.weekday == null ? 0 : Number(input.weekday);
  const monthDay = input && input.month_day == null ? 0 : Number(input.month_day);
  const planRevision = Number((input && input.plan_revision) || 1);
  if (!Number.isSafeInteger(id) || id <= 0) throw new Error('backup_schedule_id_invalid');
  if (!Number.isSafeInteger(planRevision) || planRevision <= 0) throw new Error('backup_schedule_revision_invalid');
  if (typeof enabled !== 'boolean') throw new Error('backup_schedule_enabled_invalid');
  if (!SAFE_CADENCES.has(cadence)) throw new Error('backup_schedule_cadence_invalid');
  if (!/^([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$/.test(localTime)) throw new Error('backup_schedule_time_invalid');
  if (localTime >= '02:00:00' && localTime < '03:00:00') throw new Error('backup_schedule_dst_unsafe_time');
  const fieldsValid = (cadence === 'daily' && weekday === 0 && monthDay === 0) ||
    (cadence === 'weekly' && weekday >= 1 && weekday <= 7 && monthDay === 0) ||
    (cadence === 'monthly' && weekday === 0 && monthDay >= 1 && monthDay <= 28);
  if (!fieldsValid) throw new Error('backup_schedule_cadence_fields_invalid');
  if (String(input.timezone_name || '') !== 'Europe/Warsaw') throw new Error('backup_schedule_timezone_invalid');
  return { id, enabled, cadence, local_time: localTime, weekday, month_day: monthDay, plan_revision: planRevision };
}

function scriptArgs(projectDir, mode, schedule, expectedIds = []) {
  const script = path.join(projectDir, 'operations', 'hardening', 'reconcile-backup-schedule-task.ps1');
  const args = ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', script, '-Mode', mode, '-RepositoryRoot', projectDir];
  if (mode === 'Prune') args.push('-ExpectedScheduleIds', expectedIds.join(','));
  else args.push('-ScheduleId', String(schedule.id), '-PlanRevision', String(schedule.plan_revision), '-Enabled', String(schedule.enabled), '-Cadence', schedule.cadence,
    '-LocalTime', schedule.local_time, '-Weekday', String(schedule.weekday), '-MonthDay', String(schedule.month_day));
  return args;
}

function runPowerShell(args, spawnImpl = spawn) {
  return new Promise((resolve, reject) => {
    const child = spawnImpl('powershell.exe', args, { windowsHide: true, shell: false });
    let stdout = ''; let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.on('error', reject);
    child.on('close', (code) => {
      if (code !== 0) { reject(new Error(String(stderr.trim() || 'backup_scheduler_host_failure').slice(0, 500))); return; }
      try {
        const line = stdout.split(/\r?\n/).map((item) => item.trim()).filter(Boolean).pop();
        resolve(JSON.parse(line || '{}'));
      } catch (_) { reject(new Error('backup_scheduler_response_invalid')); }
    });
  });
}

function validateScheduleList(items) {
  if (!Array.isArray(items) || items.length > MAX_SCHEDULES) throw new Error('backup_schedule_list_invalid');
  const schedules = items.map(normalizeSchedule);
  if (new Set(schedules.map((item) => item.id)).size !== schedules.length) throw new Error('backup_schedule_duplicate_id');
  return schedules;
}

async function previewSchedules(projectDir, items, spawnImpl = spawn) {
  const schedules = validateScheduleList(items);
  const results = [];
  for (const schedule of schedules) results.push(await runPowerShell(scriptArgs(projectDir, 'Preview', schedule), spawnImpl));
  return { items: results };
}

async function reconcileSchedules(projectDir, items, spawnImpl = spawn) {
  const schedules = validateScheduleList(items);
  const results = [];
  for (const schedule of schedules) results.push(await runPowerShell(scriptArgs(projectDir, 'Apply', schedule), spawnImpl));
  const prune = await runPowerShell(scriptArgs(projectDir, 'Prune', null, schedules.map((item) => item.id)), spawnImpl);
  if (Array.isArray(prune.unmanaged) && prune.unmanaged.length) throw new Error('backup_scheduler_unmanaged_task_detected');
  return { items: results, prune };
}

module.exports = { MAX_SCHEDULES, normalizeSchedule, scriptArgs, validateScheduleList, previewSchedules, reconcileSchedules };
