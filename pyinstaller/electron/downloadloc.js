
function orgName() {
    // This can be changed in order to make download possible from other github orgs
    return "cryptoadvance"
}

function getDownloadLocation(version, platformname) {
    if (platformname != "osx") {
        return `https://github.com/${orgName()}/specter-desktop/releases/download/${version}/specterd-${version}-${platformname}.zip`
    }
    return `https://github.com/${orgName()}/specter-desktop/releases/download/${version}/specterd-${version}-${platformname}_${process.arch}.zip`
}

function appName() {
    return "Specter"
}

module.exports = {
    getDownloadLocation, 
    appName,
    orgName
}

