'use strict';

const crypto = require('crypto');

const CONTRACT_V1 = 'NEXT_STABIL_ADVANCED_ANALYSIS_RESULT_V1';
const CONTRACT_V2 = 'NEXT_STABIL_TEMP_CHAT_RESULT_V2';
const ARTIFACT_V2 = 'NEXT_STABIL_TEMP_CHAT_RESULT_ARTIFACT_V2';

function object(value, code) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(code);
}

function exactKeys(value, allowed, code) {
  object(value, code);
  const keys = Object.keys(value);
  if (keys.length !== allowed.size || keys.some((key) => !allowed.has(key))) throw new Error(code);
}

function contractVersion(pkg) {
  return pkg.contract_version || CONTRACT_V1;
}

function stringList(value, limit, code) {
  if (!Array.isArray(value) || value.length > limit || value.some((item) => typeof item !== 'string')) throw new Error(code);
}

function handles(value, allowed, code, required = false) {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string')) throw new Error(code);
  if (required && value.length === 0) throw new Error(code);
  if (value.some((item) => !allowed.has(item))) throw new Error(code);
}

function scopedSources(pkg) {
  const all = new Set((pkg.sources || []).map((item) => item.source_ref));
  if (!pkg.target_scope) return all;
  const scope = pkg.target_scope;
  exactKeys(scope, new Set(['scope_handle', 'allowed_source_handles', 'global_source_handles']), 'V2_TARGET_SCOPE');
  if (!/^TARGET_0[1-8]$/.test(scope.scope_handle)) throw new Error('V2_TARGET_SCOPE');
  stringList(scope.allowed_source_handles, 8, 'V2_TARGET_SCOPE');
  stringList(scope.global_source_handles, 8, 'V2_TARGET_SCOPE');
  if (!scope.allowed_source_handles.length
      || new Set(scope.allowed_source_handles).size !== scope.allowed_source_handles.length
      || new Set(scope.global_source_handles).size !== scope.global_source_handles.length
      || scope.allowed_source_handles.some((item) => scope.global_source_handles.includes(item))
      || [...scope.allowed_source_handles, ...scope.global_source_handles].some((item) => !all.has(item))) {
    throw new Error('V2_TARGET_SCOPE');
  }
  return new Set([...scope.allowed_source_handles, ...scope.global_source_handles]);
}

function itemSources(item) {
  if (Array.isArray(item.source_handles)) return new Set(item.source_handles.filter((value) => typeof value === 'string'));
  return typeof item.source_handle === 'string' ? new Set([item.source_handle]) : new Set();
}

function manifestHandles(pkg) {
  const facts = new Set(); const tools = new Set(); const visuals = new Set();
  const sources = scopedSources(pkg);
  for (const item of pkg.claims || []) {
    if (!item || typeof item !== 'object') continue;
    if (item.kind === 'FACT' && typeof item.fact_handle === 'string'
        && sources.has(item.source_handle)) facts.add(item.fact_handle);
    const provenance = itemSources(item);
    if (item.kind === 'TOOL_RESULT' && typeof item.tool_handle === 'string'
        && provenance.size > 0 && [...provenance].every((handle) => sources.has(handle))) tools.add(item.tool_handle);
    if (item.kind === 'VISUAL_OBSERVATION' && typeof item.visual_handle === 'string'
        && Array.isArray(item.source_handles) && item.source_handles.length > 0
        && item.source_handles.every((handle) => sources.has(handle))) visuals.add(item.visual_handle);
  }
  return { facts, tools, visuals };
}

function validateV2Result(value, manifest) {
  exactKeys(value, new Set(['schema', 'claims', 'contradictions']), 'V2_SCHEMA');
  if (value.schema !== CONTRACT_V2 || !Array.isArray(value.claims)
      || value.claims.length < 1 || value.claims.length > 64
      || !Array.isArray(value.contradictions)) throw new Error('V2_SCHEMA');
  const allowed = manifestHandles(manifest.package);
  const selectedFacts = new Set();
  const relationshipCoverages = [];
  for (const claim of value.claims) {
    object(claim, 'V2_CLAIM_SCHEMA');
    if ('claim_id' in claim) throw new Error('V2_EXTERNAL_CLAIM_ID');
    if (claim.class === 'FACT') {
      exactKeys(claim, new Set(['class', 'fact_handles', 'tool_handles', 'visual_handles']), 'V2_CLAIM_SCHEMA');
      handles(claim.fact_handles || [], allowed.facts, 'V2_UNKNOWN_FACT');
      handles(claim.tool_handles || [], allowed.tools, 'V2_UNKNOWN_TOOL');
      handles(claim.visual_handles || [], allowed.visuals, 'V2_UNKNOWN_VISUAL');
      if (!(claim.fact_handles.length || claim.tool_handles.length || claim.visual_handles.length)) throw new Error('V2_MISSING_PROVENANCE');
      claim.fact_handles.forEach((handle) => selectedFacts.add(handle));
    } else if (claim.class === 'ESTIMATE') {
      const status = claim.estimate_status || (claim.confidence === 'NOT_ESTIMABLE' ? 'NOT_ESTIMABLE' : 'ESTIMABLE');
      const legacy = !Object.prototype.hasOwnProperty.call(claim, 'estimate_status');
      const expected = status === 'NOT_ESTIMABLE' && !legacy
        ? new Set(['class', 'estimate_status', 'reason', 'basis_fact_handles', 'basis_tool_handles', 'missing_inputs'])
        : new Set(['class', ...(legacy ? [] : ['estimate_status']), 'value_or_range', 'confidence', 'basis_fact_handles', 'basis_tool_handles', 'assumptions', 'missing_inputs']);
      exactKeys(claim, expected, 'V2_CLAIM_SCHEMA');
      handles(claim.basis_fact_handles || [], allowed.facts, 'V2_UNKNOWN_FACT');
      handles(claim.basis_tool_handles || [], allowed.tools, 'V2_UNKNOWN_TOOL');
      if (!(claim.basis_fact_handles.length || claim.basis_tool_handles.length)) throw new Error('V2_ESTIMATE');
      claim.basis_fact_handles.forEach((handle) => selectedFacts.add(handle));
      stringList(claim.missing_inputs, 32, 'V2_ESTIMATE');
      if (status === 'NOT_ESTIMABLE' && !legacy) {
        if (typeof claim.reason !== 'string' || !claim.reason || !claim.missing_inputs.length) throw new Error('V2_ESTIMATE');
      } else {
        if (status !== 'ESTIMABLE' || typeof claim.value_or_range !== 'string' || !claim.value_or_range
            || !['HIGH', 'MEDIUM', 'LOW'].includes(claim.confidence)) throw new Error('V2_ESTIMATE');
        stringList(claim.assumptions, 32, 'V2_ESTIMATE');
      }
    } else if (claim.class === 'HYPOTHESIS') {
      exactKeys(claim, new Set(['class', 'statement', 'support_fact_handles', 'contradiction_fact_handles', 'confirm_or_refute']), 'V2_CLAIM_SCHEMA');
      if (typeof claim.statement !== 'string' || !claim.statement
          || typeof claim.confirm_or_refute !== 'string' || !claim.confirm_or_refute) throw new Error('V2_HYPOTHESIS');
      handles(claim.support_fact_handles, allowed.facts, 'V2_UNKNOWN_FACT', true);
      handles(claim.contradiction_fact_handles || [], allowed.facts, 'V2_UNKNOWN_FACT');
      const coverage = new Set([...claim.support_fact_handles, ...(claim.contradiction_fact_handles || [])]);
      coverage.forEach((handle) => selectedFacts.add(handle));
      relationshipCoverages.push(coverage);
    } else if (claim.class === 'MISSING') {
      exactKeys(claim, new Set(['class', 'item', 'why_relevant', 'estimable']), 'V2_CLAIM_SCHEMA');
      if (typeof claim.item !== 'string' || !claim.item
          || typeof claim.why_relevant !== 'string' || !claim.why_relevant
          || typeof claim.estimable !== 'boolean') throw new Error('V2_MISSING');
    } else throw new Error('V2_CLAIM_CLASS');
  }
  for (const item of value.contradictions) {
    exactKeys(item, new Set(['description', 'fact_handles']), 'V2_CONTRADICTION');
    if (typeof item.description !== 'string' || !item.description) throw new Error('V2_CONTRADICTION');
    handles(item.fact_handles, allowed.facts, 'V2_UNKNOWN_FACT', true);
    const coverage = new Set(item.fact_handles);
    coverage.forEach((handle) => selectedFacts.add(handle));
    relationshipCoverages.push(coverage);
  }
  if (manifest.package.analysis_type === 'consistency_check') {
    const groups = new Map();
    for (const item of manifest.package.claims || []) {
      if (!item || item.kind !== 'FACT' || typeof item.fact_handle !== 'string'
          || typeof item.comparison_group !== 'string' || !allowed.facts.has(item.fact_handle)) continue;
      if (!groups.has(item.comparison_group)) groups.set(item.comparison_group, new Set());
      groups.get(item.comparison_group).add(item.fact_handle);
    }
    for (const members of groups.values()) {
      const selectedCount = [...members].filter((handle) => selectedFacts.has(handle)).length;
      const covered = relationshipCoverages.some((coverage) => [...members].every((handle) => coverage.has(handle)));
      if (selectedCount >= 2 && !covered) throw new Error('V2_CONSISTENCY_RELATIONSHIP');
    }
  }
  return value;
}

function canonicalHash(value) {
  return crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
}

function schemaTemplate() {
  return {
    schema: CONTRACT_V2,
    claims: [
      { class: 'FACT', fact_handles: ['F1'], tool_handles: [], visual_handles: [] },
      { class: 'MISSING', item: 'brakująca informacja', why_relevant: 'znaczenie', estimable: false },
      { class: 'HYPOTHESIS', statement: 'hipoteza', support_fact_handles: ['F1'], contradiction_fact_handles: [], confirm_or_refute: 'sposób weryfikacji' },
      { class: 'ESTIMATE', estimate_status: 'ESTIMABLE', value_or_range: 'wartość lub zakres', confidence: 'LOW', basis_fact_handles: ['F1'], basis_tool_handles: [], assumptions: [], missing_inputs: [] },
      { class: 'ESTIMATE', estimate_status: 'NOT_ESTIMABLE', reason: 'dlaczego nie można oszacować', basis_fact_handles: ['F1'], basis_tool_handles: [], missing_inputs: ['brakujący parametr'] },
    ],
    contradictions: [{ description: 'opis materialnej sprzeczności', fact_handles: ['F1', 'F2'] }],
  };
}

module.exports = {
  CONTRACT_V1, CONTRACT_V2, ARTIFACT_V2, contractVersion,
  scopedSources, manifestHandles, validateV2Result, canonicalHash, schemaTemplate,
};
