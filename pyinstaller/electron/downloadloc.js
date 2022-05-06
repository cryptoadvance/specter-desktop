
function getDownloadLocation(version, platformname) {
    return `https://github.com/cryptoadvance/specter-desktop/releases/download/${version}/specterd-${version}-${platformname}.zip`
}

function appName() {
    return "Specter"
}

module.exports = {
    getDownloadLocation: getDownloadLocation, 
    appName: appName
}

