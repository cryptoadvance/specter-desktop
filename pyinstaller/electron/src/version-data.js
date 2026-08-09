const SHA256_PATTERN = /^[0-9a-f]{64}$/i

function isValidSha256(value) {
  return typeof value === 'string' && SHA256_PATTERN.test(value)
}

function getSpecterdHash(versionData, arch) {
  const hash = versionData && versionData.sha256 && versionData.sha256[arch]
  return isValidSha256(hash) ? hash.toLowerCase() : null
}

function hashesMatch(expectedHash, actualHash) {
  return isValidSha256(expectedHash) && isValidSha256(actualHash) && expectedHash.toLowerCase() === actualHash.toLowerCase()
}

function synchronizeSpecterdSettings(appSettings, versionData, arch) {
  const hash = getSpecterdHash(versionData, arch)
  if (!hash) {
    return { changed: false, hash: null }
  }

  const changed =
    appSettings.specterdVersion !== versionData.version ||
    appSettings.versionInitialized !== versionData.version ||
    appSettings.specterdHash !== hash

  if (changed) {
    appSettings.specterdVersion = versionData.version
    appSettings.specterdHash = hash
    appSettings.versionInitialized = versionData.version
  }

  return { changed, hash }
}

function missingHashMessage(versionData, arch) {
  const version = versionData && versionData.version ? ` ${versionData.version}` : ''
  return `Specter release${version} does not contain a valid specterd hash for ${arch}. Please install a complete release for this platform architecture.`
}

module.exports = {
  getSpecterdHash,
  hashesMatch,
  isValidSha256,
  missingHashMessage,
  synchronizeSpecterdSettings,
}
