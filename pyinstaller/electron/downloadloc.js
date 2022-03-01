
function getDownloadLocation(version, platformname) {
    return `http://specterext.bitcoinops.de/user/k9ert/dice/releases/download/${version}/diced-${version}-${platformname}.zip`
}

function appName() {
    return "Specter"
}

module.exports = {
    getDownloadLocation: getDownloadLocation, 
    appName: appName
}

