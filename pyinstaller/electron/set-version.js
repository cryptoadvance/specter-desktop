const fs = require('fs')
const crypto = require('crypto')
const version = process.argv[2]

async function setVersion() {
    let package = require('./package.json')
    package.version = version
    fs.writeFileSync('./package.json', JSON.stringify(package, undefined, 2))
    
    if (process.argv[3]) {
        let versionData = {
            version,
            sha256: (await createHashFromFile(process.argv[3]))
        }
    
        fs.writeFileSync('./version-data.json', JSON.stringify(versionData, undefined, 2))
    }    
}

const createHashFromFile = filePath => new Promise(resolve => {
    const hash = crypto.createHash('sha256');
    fs.createReadStream(filePath).on('data', data => hash.update(data)).on('end', () => resolve(hash.digest('hex')));
});

setVersion()
