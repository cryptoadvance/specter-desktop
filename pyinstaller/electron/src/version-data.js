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
  const releaseHash = getSpecterdHash(versionData, arch)
  if (!releaseHash) {
    return { changed: false, hash: null }
  }

  // Adopt the bundled release only when this release has not been initialized
  // yet, or when the stored hash is unusable. A stored hash that is a valid
  // SHA-256 but differs from the bundled one is a deliberate user choice
  // (Preferences -> "Choose file") and has to survive restarts.
  const changed =
    appSettings.versionInitialized !== versionData.version || !isValidSha256(appSettings.specterdHash)

  if (changed) {
    appSettings.specterdVersion = versionData.version
    appSettings.specterdHash = releaseHash
    appSettings.versionInitialized = versionData.version
  }

  return { changed, hash: appSettings.specterdHash.toLowerCase() }
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
