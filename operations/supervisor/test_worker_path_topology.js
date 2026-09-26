'use strict';
const assert=require('assert');const fs=require('fs');const os=require('os');const path=require('path');const {AnalysisQueue}=require('./analysis_queue');
const source=fs.readFileSync(path.join(__dirname,'server.js'),'utf8');
assert.match(source,/operations', 'vision-worker/);assert.match(source,/data', 'workers', 'chatgpt-vision/);
assert.doesNotMatch(source,/D:\\\\ai-lab-data\\\\workers/);assert.doesNotMatch(source,/path\.join\(VISION_WORKER_STATE_ROOT, 'worker'/);
const root=fs.mkdtempSync(path.join(os.tmpdir(),'next-worker-path-'));const code=path.join(root,'code');const state=path.join(root,'data','workers','chatgpt-vision');const spool=path.join(root,'data','analysis-spool');fs.mkdirSync(path.join(code,'node_modules'),{recursive:true});fs.mkdirSync(state,{recursive:true});
const queue=new AnalysisQueue({spoolRoot:spool,workerScript:path.join(code,'analysis-job.js'),workerRoot:state,workerModulesRoot:code,spawnWorker:()=>{throw new Error('fixture_only');}});
assert.strictEqual(queue.workerRoot,state);assert.strictEqual(queue.workerModulesRoot,code);assert.ok(queue.jobs.startsWith(spool));
fs.rmSync(root,{recursive:true,force:true});process.stdout.write('WORKER CODE/STATE PATH TOPOLOGY: PASS\n');
