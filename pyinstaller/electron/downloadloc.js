
function orgName() {
    return "k9ert"
}

function getDownloadLocation(version, platformname) {
    if (platformname != "darwin") {
        return `https://github.com/${orgName()}/specter-desktop/releases/download/${version}/specterd-${version}-${platformname}.zip`
    }
    return `https://github.com/${orgName()}/specter-desktop/releases/download/${version}/specterd-${version}-${platformname}_${process.arch}.zip`
}

function appName() {
    return "Specter"
}

module.exports = {
    getDownloadLocation: getDownloadLocation, 
    appName: appName
}

