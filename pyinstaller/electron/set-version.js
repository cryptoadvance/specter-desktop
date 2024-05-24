/*
    This will set the version for package.json and might also create a version-data.json file



*/

const fs = require('fs')
const crypto = require('crypto')
const versionDataFile = './version-data.json'

async function setVersion() {
    const version = process.argv[2]
    const file = process.argv[4]

    // Set version in package.json
    let package = require('./package.json')
    package.version = version
    fs.writeFileSync('./package.json', JSON.stringify(package, undefined, 2))
    
    // Set version in version-data.json
    if (arch && file) {
        let versionData
        try {
           versionData = require(versionDataFile)
        } catch (error) {
            console.log(`No ${versionDataFile} found. Creating anew`)
            versionData = {
                version,
                sha256: {}
            }
        }
        if (versionData.version != version) {
            throw new Error(`param version ${version} and version from versionData ${versionData.version} does not match`)
        }
        versionData.sha256[process.arch] = (await createHashFromFile(file))
    
        fs.writeFileSync(versionDataFile, JSON.stringify(versionData, undefined, 2))
        console.log(versionData)
    } else if (arch || file) {
        throw new Error("Declare arch and file or none")
    }

}

const createHashFromFile = filePath => new Promise(resolve => {
    const hash = crypto.createHash('sha256');
    fs.createReadStream(filePath).on('data', data => hash.update(data)).on('end', () => resolve(hash.digest('hex')));
});

setVersion()
