'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const source = fs.readFileSync(
  path.join(__dirname, 'public_web_server.cjs'),
  'utf8',
);

assert.match(source, /X-Content-Type-Options': 'nosniff'/);
assert.match(source, /Referrer-Policy': 'strict-origin-when-cross-origin'/);
assert.match(source, /X-Frame-Options': 'DENY'/);
assert.match(source, /Content-Security-Policy-Report-Only/);
assert.match(source, /frame-ancestors 'none'/);
assert.doesNotMatch(source, /Strict-Transport-Security/);

new vm.Script(source, { filename: 'public_web_server.cjs' });

process.stdout.write('CHUNK20_PUBLIC_SECURITY_HEADERS_SOURCE=PASS\n');
process.stdout.write('CHUNK20_HSTS=DEFERRED\n');
