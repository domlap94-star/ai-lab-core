'use strict';
class TemporaryChatArbiter {
  constructor() { this.owner = null; this.waiters = []; this.pausedState = null; }
  acquire(kind, jobId, callback) { const lease={kind,jobId,callback}; if(!this.owner&&!this.pausedState){this.owner=lease;callback();return true;} this.waiters.push(lease);return false; }
  release(kind, jobId) { if(!this.owner||this.owner.kind!==kind||this.owner.jobId!==jobId)return false;this.owner=null;this._dispatch();return true; }
  pause(state) { this.pausedState=state; }
  resume() { this.pausedState=null;this._dispatch(); }
  _dispatch() { if(this.owner||this.pausedState)return;const next=this.waiters.shift();if(next){this.owner=next;setImmediate(next.callback);} }
  cancel(kind, jobId) { this.waiters=this.waiters.filter((x)=>x.kind!==kind||x.jobId!==jobId); }
  health() { return {owner_type:this.owner?.kind||null,owner_job_id:this.owner?.jobId||null,waiting:this.waiters.length,paused_state:this.pausedState}; }
}
module.exports={TemporaryChatArbiter};
