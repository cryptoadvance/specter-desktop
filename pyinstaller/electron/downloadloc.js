function getDownloadLocation(version, platformname) {
    return `https://github.com/cryptoadvance/specter-desktop/releases/download/${version}/specterd-${version}-${platformname}.zip`
}

module.exports = {
    getDownloadLocation: getDownloadLocation
}