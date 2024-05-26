const fs = require('fs');
const crypto = require('crypto');
const versionDataFile = './version-data.json';

async function setVersion() {
  const version = process.argv[2];
  const file = process.argv[3];
  const arch = process.argv[4] || process.arch;

  // Set version in package.json
  let packageJson = require('./package.json');
  packageJson.version = version;
  fs.writeFileSync('./package.json', JSON.stringify(packageJson, undefined, 2));

  // Set version in version-data.json
  if (version && file) {
    let versionData;
    try {
      versionData = require(versionDataFile);
      
      if (versionData.version != version) {
        console.log(`Version mismatch. Deleting ${versionDataFile} and creating anew.`);
        fs.unlinkSync(versionDataFile); // Delete the existing version-data.json file
        versionData = createNewVersionData(version); // Create new version data object
      }
      
    } catch (error) {
      console.log(`No ${versionDataFile} found. Creating anew.`);
      versionData = createNewVersionData(version);
    }
    // Compute SHA256 hash of the provided file
    versionData.sha256[arch] = await createHashFromFile(file);
    // Write new version data to file
    fs.writeFileSync(versionDataFile, JSON.stringify(versionData, undefined, 2));
    console.log("version-data.js: ")
    console.log("----------------------------------------------------------")
    console.log(versionData);
    console.log("----------------------------------------------------------")
  } else if (arch || file) {
    throw new Error("Declare both arch and file or none.");
  }
}

function createNewVersionData(version) {
  // Return a new version data object
  return {
    version,
    sha256: {}
  };
}

const createHashFromFile = filePath => new Promise((resolve, reject) => {
  const hash = crypto.createHash('sha256');
  fs.createReadStream(filePath)
    .on('data', data => hash.update(data))
    .on('end', () => resolve(hash.digest('hex')))
    .on('error', reject);
});

setVersion().catch(console.error);