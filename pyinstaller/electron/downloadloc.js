
const DEFAULT_REPOSITORY = 'cryptoadvance/specter-desktop'
const REPOSITORY_PATTERN = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/

function repositoryName(repository = DEFAULT_REPOSITORY) {
    if (!REPOSITORY_PATTERN.test(repository)) {
        throw new Error(`Invalid specterd download repository: ${repository}`)
    }
    return repository
}

function orgName() {
    return DEFAULT_REPOSITORY.split('/')[0]
}

function getDownloadLocation(version, platformname, arch = process.arch, repository = DEFAULT_REPOSITORY) {
    const releaseRepository = repositoryName(repository)
    if (platformname != "osx") {
        return `https://github.com/${releaseRepository}/releases/download/${version}/specterd-${version}-${platformname}.zip`
    }
    return `https://github.com/${releaseRepository}/releases/download/${version}/specterd-${version}-${platformname}_${arch}.zip`
}

function appName() {
    return "Specter"
}

module.exports = {
    getDownloadLocation, 
    appName,
    orgName,
    repositoryName,
}
