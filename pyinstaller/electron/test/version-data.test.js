const assert = require('node:assert/strict')
const test = require('node:test')

const {
  getSpecterdHash,
  hashesMatch,
  isValidSha256,
  missingHashMessage,
  synchronizeSpecterdSettings,
} = require('../src/version-data')

const X64_HASH = 'a'.repeat(64)
const ARM64_HASH = 'B'.repeat(64)

test('selects and normalizes the hash for each Electron architecture', () => {
  const versionData = { version: 'v2.1.11-pre1', sha256: { x64: X64_HASH, arm64: ARM64_HASH } }

  assert.equal(getSpecterdHash(versionData, 'x64'), X64_HASH)
  assert.equal(getSpecterdHash(versionData, 'arm64'), ARM64_HASH.toLowerCase())
})

test('rejects missing, empty, malformed, and non-string architecture hashes', () => {
  for (const hash of [undefined, null, '', 'unknown', 'a'.repeat(63), 42]) {
    assert.equal(getSpecterdHash({ sha256: { x64: hash } }, 'x64'), null)
    assert.equal(isValidSha256(hash), false)
  }
})

test('hash comparison fails closed unless both values are valid SHA-256 strings', () => {
  assert.equal(hashesMatch(X64_HASH.toUpperCase(), X64_HASH), true)
  assert.equal(hashesMatch('', ''), false)
  assert.equal(hashesMatch(undefined, X64_HASH), false)
  assert.equal(hashesMatch(X64_HASH, 'not-a-hash'), false)
})

test('missing hash errors identify the release and host architecture', () => {
  assert.match(missingHashMessage({ version: 'v2.1.11-pre1' }, 'x64'), /v2\.1\.11-pre1/)
  assert.match(missingHashMessage({ version: 'v2.1.11-pre1' }, 'x64'), /x64/)
})

test('refreshes stale launcher settings without disturbing unrelated user settings', () => {
  const settings = {
    basicAuthUser: 'alice',
    specterdHash: null,
    specterdVersion: 'v2.1.10',
    versionInitialized: 'v2.1.10',
  }
  const versionData = { version: 'v2.1.11-pre1', sha256: { x64: X64_HASH } }

  assert.deepEqual(synchronizeSpecterdSettings(settings, versionData, 'x64'), { changed: true, hash: X64_HASH })
  assert.equal(settings.basicAuthUser, 'alice')
  assert.equal(settings.specterdHash, X64_HASH)
  assert.equal(settings.specterdVersion, 'v2.1.11-pre1')
  assert.equal(settings.versionInitialized, 'v2.1.11-pre1')
})

test('keeps a user-supplied specterd binary hash across restarts', () => {
  const customHash = 'c'.repeat(64)
  const settings = {
    specterdHash: customHash,
    specterdVersion: 'v2.1.11-pre1',
    versionInitialized: 'v2.1.11-pre1',
  }
  const versionData = { version: 'v2.1.11-pre1', sha256: { x64: X64_HASH } }

  assert.deepEqual(synchronizeSpecterdSettings(settings, versionData, 'x64'), {
    changed: false,
    hash: customHash,
  })
  assert.equal(settings.specterdHash, customHash)
})

test('repairs an unusable stored hash without waiting for the next release', () => {
  const settings = { specterdHash: '', specterdVersion: 'v2.1.11-pre1', versionInitialized: 'v2.1.11-pre1' }
  const versionData = { version: 'v2.1.11-pre1', sha256: { x64: X64_HASH } }

  assert.deepEqual(synchronizeSpecterdSettings(settings, versionData, 'x64'), { changed: true, hash: X64_HASH })
  assert.equal(settings.specterdHash, X64_HASH)
})

test('does not mutate settings when the release hash is missing', () => {
  const settings = { specterdHash: 'stale', specterdVersion: 'v2.1.10' }
  const original = { ...settings }

  assert.deepEqual(synchronizeSpecterdSettings(settings, { version: 'v2.1.11', sha256: {} }, 'x64'), {
    changed: false,
    hash: null,
  })
  assert.deepEqual(settings, original)
})
