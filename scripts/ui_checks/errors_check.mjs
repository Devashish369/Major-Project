// Checks frontend/src/api/errors.js with the response shapes the API really returns.  Run: node scripts/ui_checks/errors_check.mjs
import { errorMessage } from '../../frontend/src/api/errors.js';
import assert from 'node:assert/strict';

const resp = (data, status = 422) => ({ response: { status, data } });
const list422 = [{ type: 'value_error', loc: ['body', 'username'], msg: 'Value error, Username may only contain letters, digits, and underscores.' }];

// 422 with the standard envelope: readable message wins
assert.equal(errorMessage(resp({ success: false, message: 'Validation failed. username: Username may only contain letters, digits, and underscores.', errors: [], detail: list422 })),
  'Validation failed. username: Username may only contain letters, digits, and underscores.');
// 422 in the OLD shape (detail is a LIST of objects): must become a string, never an array
const old = errorMessage(resp({ detail: list422 }));
assert.equal(typeof old, 'string'); assert.match(old, /Username may only contain/);
// plain HTTP errors
assert.equal(errorMessage(resp({ success: false, message: 'Not Found', detail: 'Not Found' }, 404)), 'Not Found');
assert.equal(errorMessage(resp({ detail: 'User is already a member.' }, 409)), 'User is already a member.');
// no response (server asleep / offline / CORS)
assert.match(errorMessage({ request: {}, message: 'Network Error' }), /Cannot reach the server/);
// junk in, string out
for (const bad of [undefined, null, {}, resp(null, 500), resp({ detail: { weird: true } }, 500), resp({ message: ['a', { msg: 'b' }] }, 500)]) {
  assert.equal(typeof errorMessage(bad, 'fallback'), 'string');
}
assert.equal(errorMessage(resp(null, 500), 'fallback'), 'fallback');
console.log('errors.js: all checks passed');
