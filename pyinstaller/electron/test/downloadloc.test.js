const assert = require('node:assert/strict')
const test = require('node:test')

const { getDownloadLocation, repositoryName } = require('../downloadloc')

test('builds repository-relative Intel and ARM macOS daemon URLs', () => {
  assert.equal(
    getDownloadLocation('v2.1.11-pre1', 'osx', 'x64', 'example/specter-desktop'),
    'https://github.com/example/specter-desktop/releases/download/v2.1.11-pre1/specterd-v2.1.11-pre1-osx_x64.zip'
  )
  assert.equal(
    getDownloadLocation('v2.1.11-pre1', 'osx', 'arm64', 'example/specter-desktop'),
    'https://github.com/example/specter-desktop/releases/download/v2.1.11-pre1/specterd-v2.1.11-pre1-osx_arm64.zip'
  )
})

test('keeps upstream as the compatibility default', () => {
  assert.equal(repositoryName(), 'cryptoadvance/specter-desktop')
})

test('rejects malformed repository metadata', () => {
  assert.throws(() => repositoryName('https://example.com/attacker/repo'), /Invalid specterd download repository/)
  assert.throws(() => repositoryName('../..'), /Invalid specterd download repository/)
  assert.throws(() => repositoryName('cryptoadvance/..'), /Invalid specterd download repository/)
})
