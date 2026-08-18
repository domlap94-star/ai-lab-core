'use strict';

const assert = require('assert');
const { extractEnvelope, validateManifest, validateResult } = require('./vision_contract');
const { parseAndValidateResponse } = require('./vision-job');

const manifest = {
  schema_version: 'NEXT_STABIL_VISION_JOB_V1', job_id: '12345678-1234-1234-1234-123456789abc',
  analysis_goal: 'technical_visual_analysis',
  sources: [{ source_ref: 'S1', document_id: 1, page_number: null, asset_id: null, sha256: 'a'.repeat(64), relative_input_path: 'input/S1.png' }],
};
validateManifest(manifest);
const result = {
  schema_version: 'NEXT_STABIL_VISION_V1', job_id: manifest.job_id,
  observations: [{ source_ref: 'S1', text: 'Widoczna linia.' }], possible_interpretations: [], uncertainties: [], visible_text: [], measurements: [],
  image_quality: [{ source_ref: 'S1', quality: 'good' }],
};
validateResult(result, manifest);
assert.deepStrictEqual(extractEnvelope(`x NEXT_STABIL_JSON_BEGIN\n\`\`\`json\n${JSON.stringify(result)}\n\`\`\`\nNEXT_STABIL_JSON_END y`), result);
assert.throws(() => extractEnvelope('{}'), /RESULT_ENVELOPE_MISSING/);
assert.throws(() => extractEnvelope('NEXT_STABIL_JSON_BEGIN {}'), /RESULT_ENVELOPE_INCOMPLETE/);
assert.throws(() => extractEnvelope('NEXT_STABIL_JSON_BEGIN { NEXT_STABIL_JSON_END'), /MALFORMED_JSON/);
assert.deepStrictEqual(
  parseAndValidateResponse(`NEXT_STABIL_JSON_BEGIN\n${JSON.stringify(result)}\nNEXT_STABIL_JSON_END`, manifest),
  result,
);
assert.throws(
  () => parseAndValidateResponse(`NEXT_STABIL_JSON_BEGIN\n${JSON.stringify({ ...result, job_id: 'wrong' })}\nNEXT_STABIL_JSON_END`, manifest),
  /SCHEMA_INVALID/,
);
assert.throws(
  () => parseAndValidateResponse(`NEXT_STABIL_JSON_BEGIN\n${JSON.stringify({ ...result, observations: [{ source_ref: 'S99', text: 'x' }] })}\nNEXT_STABIL_JSON_END`, manifest),
  /UNKNOWN_SOURCE_REF/,
);
assert.throws(() => validateResult({ ...result, observations: [{ source_ref: 'S99', text: 'x' }] }, manifest), /UNKNOWN_SOURCE/);
assert.throws(() => validateResult({ ...result, measurements: [{ source_ref: 'S1', value: 3, unit: 'mm' }] }, manifest), /BASIS/);
assert.throws(() => validateManifest({ ...manifest, sources: [{ ...manifest.sources[0], relative_input_path: '../x.png' }] }), /INPUT_PATH/);
process.stdout.write('VISION WORKER CONTRACT TESTS: OK\n');
