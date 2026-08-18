'use strict';

const fs = require('fs');
const crypto = require('crypto');

const JOB_SCHEMA = 'NEXT_STABIL_VISION_JOB_V1';
const RESULT_SCHEMA = 'NEXT_STABIL_VISION_V1';
const MAX_SOURCES = 4;
const MAX_ITEMS = 40;
const MAX_TEXT = 2000;
const MAX_RESPONSE_CHARS = 100000;

function requireObject(value, code) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(code);
}

function validateManifest(value) {
  requireObject(value, 'MANIFEST_NOT_OBJECT');
  if (value.schema_version !== JOB_SCHEMA) throw new Error('MANIFEST_VERSION');
  if (!/^[a-f0-9-]{16,64}$/i.test(String(value.job_id || ''))) throw new Error('MANIFEST_JOB_ID');
  if (value.analysis_goal !== 'technical_visual_analysis') throw new Error('MANIFEST_GOAL');
  if (!Array.isArray(value.sources) || value.sources.length < 1 || value.sources.length > MAX_SOURCES) throw new Error('MANIFEST_SOURCES');
  const refs = new Set();
  for (const source of value.sources) {
    requireObject(source, 'MANIFEST_SOURCE');
    if (!/^S[1-4]$/.test(String(source.source_ref || '')) || refs.has(source.source_ref)) throw new Error('MANIFEST_SOURCE_REF');
    refs.add(source.source_ref);
    if (!Number.isInteger(source.document_id) || source.document_id < 1) throw new Error('MANIFEST_DOCUMENT_ID');
    if (source.page_number != null && (!Number.isInteger(source.page_number) || source.page_number < 1)) throw new Error('MANIFEST_PAGE_NUMBER');
    if (source.asset_id != null && (!Number.isInteger(source.asset_id) || source.asset_id < 1)) throw new Error('MANIFEST_ASSET_ID');
    if (!/^[a-f0-9]{64}$/i.test(String(source.sha256 || ''))) throw new Error('MANIFEST_SHA256');
    if (!/^input\/S[1-4]\.[a-z0-9]{1,8}$/i.test(String(source.relative_input_path || '').replace(/\\/g, '/'))) throw new Error('MANIFEST_INPUT_PATH');
  }
  return refs;
}

function validateResult(value, manifest) {
  requireObject(value, 'RESULT_NOT_OBJECT');
  const allowed = new Set(['schema_version', 'job_id', 'observations', 'possible_interpretations', 'uncertainties', 'visible_text', 'measurements', 'image_quality']);
  if (Object.keys(value).some((key) => !allowed.has(key))) throw new Error('RESULT_UNKNOWN_FIELD');
  if (value.schema_version !== RESULT_SCHEMA) throw new Error('RESULT_VERSION');
  if (value.job_id !== manifest.job_id) throw new Error('RESULT_JOB_ID');
  const refs = validateManifest(manifest);
  for (const key of ['observations', 'possible_interpretations', 'uncertainties', 'visible_text']) {
    if (!Array.isArray(value[key]) || value[key].length > MAX_ITEMS) throw new Error(`RESULT_${key.toUpperCase()}`);
    for (const item of value[key]) {
      requireObject(item, `RESULT_${key.toUpperCase()}_ITEM`);
      if (!refs.has(item.source_ref)) throw new Error('RESULT_UNKNOWN_SOURCE');
      if (typeof item.text !== 'string' || item.text.trim().length < 1 || item.text.length > MAX_TEXT) throw new Error('RESULT_TEXT');
    }
  }
  if (!Array.isArray(value.image_quality) || value.image_quality.length !== manifest.sources.length) throw new Error('RESULT_IMAGE_QUALITY');
  const qualityRefs = new Set();
  for (const item of value.image_quality) {
    requireObject(item, 'RESULT_IMAGE_QUALITY_ITEM');
    if (!refs.has(item.source_ref) || qualityRefs.has(item.source_ref)) throw new Error('RESULT_IMAGE_QUALITY_SOURCE');
    qualityRefs.add(item.source_ref);
    if (!['good', 'limited', 'poor'].includes(item.quality)) throw new Error('RESULT_IMAGE_QUALITY_ENUM');
  }
  if (!Array.isArray(value.measurements) || value.measurements.length > 12) throw new Error('RESULT_MEASUREMENTS');
  for (const item of value.measurements) {
    requireObject(item, 'RESULT_MEASUREMENT_ITEM');
    if (!refs.has(item.source_ref)) throw new Error('RESULT_UNKNOWN_SOURCE');
    if (item.basis !== 'visible_scale') throw new Error('RESULT_MEASUREMENT_BASIS');
    if (typeof item.value !== 'number' || !Number.isFinite(item.value)) throw new Error('RESULT_MEASUREMENT_VALUE');
    if (typeof item.unit !== 'string' || item.unit.length < 1 || item.unit.length > 20) throw new Error('RESULT_MEASUREMENT_UNIT');
  }
  return value;
}

function extractEnvelope(text) {
  if (typeof text !== 'string') throw new Error('RESULT_ENVELOPE_MISSING');
  if (text.length > MAX_RESPONSE_CHARS) throw new Error('SCHEMA_INVALID');
  const begin = 'NEXT_STABIL_JSON_BEGIN';
  const end = 'NEXT_STABIL_JSON_END';
  const start = text.indexOf(begin);
  if (start < 0) throw new Error('RESULT_ENVELOPE_MISSING');
  const finish = text.indexOf(end, start + begin.length);
  if (finish < 0 || finish <= start) throw new Error('RESULT_ENVELOPE_INCOMPLETE');
  let body = text.slice(start + begin.length, finish).trim();
  const fence = body.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  if (fence) body = fence[1].trim();
  try {
    return JSON.parse(body);
  } catch (_) {
    throw new Error('MALFORMED_JSON');
  }
}

function sha256File(filePath) {
  const hash = crypto.createHash('sha256');
  hash.update(fs.readFileSync(filePath));
  return hash.digest('hex');
}

function sha256Json(value) {
  return crypto.createHash('sha256').update(`${JSON.stringify(value)}\n`, 'utf8').digest('hex');
}

module.exports = { JOB_SCHEMA, RESULT_SCHEMA, MAX_SOURCES, MAX_RESPONSE_CHARS, validateManifest, validateResult, extractEnvelope, sha256File, sha256Json };
