'use strict';
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const helper = fs.readFileSync(path.join(__dirname, '..', 'hardening', 'invoke-qdrant-backup-helper.ps1'), 'utf8');
const backup = fs.readFileSync(path.join(__dirname, '..', 'hardening', 'backup-production.ps1'), 'utf8');

assert.match(helper, /NEXT_STABIL_QDRANT_BACKUP_HELPER_REQUEST_V1/);
assert.match(helper, /NEXT_STABIL_QDRANT_BACKUP_HELPER_RESULT_V1/);
assert.match(helper, /Resolve-NsR26CollectionSnapshotPath/);
assert.match(helper, /Join-Path \$collectionRoot \$SnapshotName/);
assert.match(helper, /SNAPSHOT_REPARSE_REJECTED/);
assert.match(helper, /'stop', '-t', '60', 'qdrant'/);
assert.match(helper, /'--pull', 'never'/);
assert.match(helper, /source=\$volume,target=\/qdrant\/storage/);
assert.match(helper, /QDRANT__STORAGE__SNAPSHOTS_PATH=\/qdrant\/snapshots/);
assert.match(helper, /QDRANT__STORAGE__TEMP_PATH=\/qdrant\/snapshots\/temp/);
assert.ok(helper.indexOf("'stop', '-t', '60', 'qdrant'") < helper.indexOf("'run', '-d', '--name'"));
assert.ok(helper.indexOf("docker.exe rm -f $helperName") < helper.indexOf("'start', 'qdrant'"));
assert.match(helper, /QDRANT_PRIMARY_IDENTITY_CHANGED/);
assert.match(helper, /QDRANT_POST_STATE_MISMATCH/);
assert.match(helper, /staging_residue_count/);
assert.match(helper, /helper_container_residue_count/);
assert.match(backup, /Invoke-QdrantHelperProcess/);
assert.match(backup, /ReadToEndAsync/);
assert.match(backup, /qdrant-helper-result\.json/);
assert.match(backup, /valid_external_f_staging/);
console.log('QDRANT_BACKUP_HELPER_CONTRACT=PASS');
