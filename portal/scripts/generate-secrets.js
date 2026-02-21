/**
 * ============================================================
 * generate-secrets.js
 * ============================================================
 * Utility script to generate secure secrets for the portal.
 *
 * Usage (run from the portal/ directory):
 *   node scripts/generate-secrets.js
 *
 * Optional — pass a custom password as the first argument:
 *   node scripts/generate-secrets.js mySecurePassword
 * ============================================================
 */

'use strict';

const crypto = require('crypto');
const bcrypt = require('bcryptjs');
const readline = require('readline');

const BCRYPT_ROUNDS = 12;
const SESSION_SECRET_BYTES = 64;

/**
 * Generates a cryptographically secure hex session secret.
 * @returns {string}
 */
function generateSessionSecret() {
  return crypto.randomBytes(SESSION_SECRET_BYTES).toString('hex');
}

/**
 * Hashes a plain-text password with bcrypt.
 * @param {string} password
 * @returns {Promise<string>}
 */
async function hashPassword(password) {
  return bcrypt.hash(password, BCRYPT_ROUNDS);
}

async function promptPassword() {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });
    rl.question('Enter the admin password to hash (input hidden): ', (answer) => {
      rl.close();
      resolve(answer.trim());
    });
    // Hide input if running interactively in a real TTY
    if (process.stdin.isTTY) {
      process.stdin.setRawMode(false);
    }
  });
}

async function main() {
  const sessionSecret = generateSessionSecret();

  // Accept password from CLI arg or prompt interactively
  let password = process.argv[2];
  if (!password) {
    password = await promptPassword();
  }

  if (!password) {
    console.error('\n❌  No password provided. Exiting.');
    process.exit(1);
  }

  console.log('\n⏳  Hashing password (this may take a moment)...\n');
  const passwordHash = await hashPassword(password);

  console.log('='.repeat(62));
  console.log('✅  Secrets generated — copy these into your portal/.env');
  console.log('='.repeat(62));
  console.log('\nSESSION_SECRET=' + sessionSecret);
  console.log('\nADMIN_PASSWORD_HASH=' + passwordHash);
  console.log('\n' + '='.repeat(62));
  console.log('⚠️   Never commit these values to version control.');
  console.log('='.repeat(62) + '\n');
}

main().catch((err) => {
  console.error('Error generating secrets:', err.message);
  process.exit(1);
});
