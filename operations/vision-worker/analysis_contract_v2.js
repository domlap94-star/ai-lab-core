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
  if (Object.keys(value).some((key) => !allowed.has(key))) throw new Error(code);
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

function manifestHandles(pkg) {
  const facts = new Set(); const tools = new Set(); const visuals = new Set();
  const sources = new Set((pkg.sources || [])
    .filter((item) => item && typeof item === 'object'
      && (typeof item.source_handle === 'string' || typeof item.source_ref === 'string'))
    .map((item) => item.source_handle || item.source_ref));
  for (const item of pkg.claims || []) {
    if (!item || typeof item !== 'object') continue;
    if (item.kind === 'FACT' && typeof item.fact_handle === 'string'
        && sources.has(item.source_handle)) facts.add(item.fact_handle);
    if (item.kind === 'TOOL_RESULT' && typeof item.tool_handle === 'string'
        && sources.has(item.source_handle)) tools.add(item.tool_handle);
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
  for (const claim of value.claims) {
    object(claim, 'V2_CLAIM_SCHEMA');
    if ('claim_id' in claim) throw new Error('V2_EXTERNAL_CLAIM_ID');
    if (claim.class === 'FACT') {
      exactKeys(claim, new Set(['class', 'fact_handles', 'tool_handles', 'visual_handles']), 'V2_CLAIM_SCHEMA');
      handles(claim.fact_handles || [], allowed.facts, 'V2_UNKNOWN_FACT');
      handles(claim.tool_handles || [], allowed.tools, 'V2_UNKNOWN_TOOL');
      handles(claim.visual_handles || [], allowed.visuals, 'V2_UNKNOWN_VISUAL');
      if (!(claim.fact_handles.length || claim.tool_handles.length || claim.visual_handles.length)) throw new Error('V2_MISSING_PROVENANCE');
    } else if (claim.class === 'ESTIMATE') {
      exactKeys(claim, new Set(['class', 'value_or_range', 'confidence', 'basis_fact_handles', 'basis_tool_handles', 'assumptions', 'missing_inputs']), 'V2_CLAIM_SCHEMA');
      if (typeof claim.value_or_range !== 'string' || !claim.value_or_range
          || !['HIGH', 'MEDIUM', 'LOW', 'NOT_ESTIMABLE'].includes(claim.confidence)) throw new Error('V2_ESTIMATE');
      handles(claim.basis_fact_handles || [], allowed.facts, 'V2_UNKNOWN_FACT');
      handles(claim.basis_tool_handles || [], allowed.tools, 'V2_UNKNOWN_TOOL');
      if (!(claim.basis_fact_handles.length || claim.basis_tool_handles.length)) throw new Error('V2_ESTIMATE');
      stringList(claim.assumptions, 32, 'V2_ESTIMATE');
      stringList(claim.missing_inputs, 32, 'V2_ESTIMATE');
    } else if (claim.class === 'HYPOTHESIS') {
      exactKeys(claim, new Set(['class', 'statement', 'support_fact_handles', 'contradiction_fact_handles', 'confirm_or_refute']), 'V2_CLAIM_SCHEMA');
      if (typeof claim.statement !== 'string' || !claim.statement
          || typeof claim.confirm_or_refute !== 'string' || !claim.confirm_or_refute) throw new Error('V2_HYPOTHESIS');
      handles(claim.support_fact_handles, allowed.facts, 'V2_UNKNOWN_FACT', true);
      handles(claim.contradiction_fact_handles || [], allowed.facts, 'V2_UNKNOWN_FACT');
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
      { class: 'ESTIMATE', value_or_range: 'wartość lub zakres', confidence: 'LOW', basis_fact_handles: ['F1'], basis_tool_handles: [], assumptions: [], missing_inputs: [] },
    ],
    contradictions: [],
  };
}

module.exports = {
  CONTRACT_V1, CONTRACT_V2, ARTIFACT_V2, contractVersion,
  validateV2Result, canonicalHash, schemaTemplate,
};
