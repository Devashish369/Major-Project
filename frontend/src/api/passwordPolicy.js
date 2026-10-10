/**
 * api/passwordPolicy.js – the same password rules as the backend (app/schemas.py), checked in the
 * browser first so people get a plain message without waiting for the server.
 */
const COMMON = new Set([
  'password', 'password1', 'password123', 'passw0rd', '12345678', '123456789', '1234567890',
  'qwerty123', 'qwertyuiop', 'iloveyou1', 'admin123', 'welcome1', 'welcome123', 'letmein1',
  'abc12345', 'abcd1234', '11111111', '00000000', 'asdf1234', 'india123', 'test1234',
]);

/** Returns a message describing the first problem, or '' when the password is acceptable. */
export function passwordProblem(password, { username = '', email = '' } = {}) {
  if (password.length < 8) return 'Password must be at least 8 characters.';
  if (new TextEncoder().encode(password).length > 72) return 'Password must be at most 72 characters.';
  if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) return 'Password must contain at least one letter and one number.';
  if (COMMON.has(password.toLowerCase())) return 'This password is too common. Please choose another one.';
  const p = password.toLowerCase();
  if (username.length >= 4 && p.includes(username.toLowerCase())) return 'Password must not contain your username.';
  const local = (email.split('@')[0] || '').toLowerCase();
  if (local.length >= 4 && p.includes(local)) return 'Password must not contain your email address.';
  return '';
}
