'use strict';

const assert = require('assert');
const { EventEmitter } = require('events');
const { normalizeSchedule, scriptArgs, validateScheduleList, reconcileSchedules } = require('./backup_scheduler');

function schedule(overrides = {}) {
  return { id: 7, enabled: true, cadence: 'daily', local_time: '03:00:00', weekday: null, month_day: null, timezone_name: 'Europe/Warsaw', ...overrides };
}

function fakeSpawn(records) {
  return (_command, args) => {
    records.push(args);
    const child = new EventEmitter();
    child.stdout = new EventEmitter(); child.stderr = new EventEmitter();
    process.nextTick(() => { child.stdout.emit('data', Buffer.from(JSON.stringify({ sync_status: 'synced', unmanaged: [] }) + '\n')); child.emit('close', 0); });
    return child;
  };
}

(async () => {
  assert.strictEqual(normalizeSchedule(schedule()).weekday, 0);
  assert.strictEqual(normalizeSchedule(schedule({ cadence: 'weekly', weekday: 1 })).weekday, 1);
  assert.strictEqual(normalizeSchedule(schedule({ cadence: 'monthly', month_day: 28 })).month_day, 28);
  assert.throws(() => normalizeSchedule(schedule({ cadence: 'monthly', month_day: 29 })), /cadence_fields/);
  assert.throws(() => normalizeSchedule(schedule({ local_time: '02:30:00' })), /dst_unsafe/);
  assert.throws(() => validateScheduleList(Array.from({ length: 11 }, (_, index) => schedule({ id: index + 1 }))), /list_invalid/);
  const args = scriptArgs('C:\\ai-lab-core', 'Apply', normalizeSchedule(schedule()));
  assert(args.includes('-ScheduleId') && args.includes('7'));
  assert(!args.some((item) => item.includes('destination') || item.includes('secret')));
  const records = [];
  await reconcileSchedules('C:\\ai-lab-core', [schedule()], fakeSpawn(records));
  assert.strictEqual(records.length, 2);
  assert(records[1].includes('-ExpectedScheduleIds'));
  console.log('BACKUP_SCHEDULER_TESTS=PASS');
})().catch((error) => { console.error(error); process.exitCode = 1; });
