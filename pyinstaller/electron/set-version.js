const fs = require('fs');
const crypto = require('crypto');
const versionDataFile = './version-data.json';
const { isValidSha256 } = require('./src/version-data');

async function setVersion() {
  const version = process.argv[2];
  const file = process.argv[3];
  const arch = process.argv[4] || process.arch;
  const repository = process.argv[5] || process.env.GITHUB_REPOSITORY || 'cryptoadvance/specter-desktop';

  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository)) {
    throw new Error(`Invalid release repository: ${repository}`);
  }

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
        versionData = createNewVersionData(version, repository); // Create new version data object
      }
      
    } catch (error) {
      console.log(`No ${versionDataFile} found. Creating anew.`);
      versionData = createNewVersionData(version, repository);
    }
    // Compute SHA256 hash of the provided file
    const fileHash = await createHashFromFile(file);
    if (!isValidSha256(fileHash)) {
      throw new Error(`Could not generate a valid SHA-256 hash for ${file}`);
    }
    versionData.sha256[arch] = fileHash;
    versionData.repository = repository;
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

function createNewVersionData(version, repository) {
  // Return a new version data object
  return {
    version,
    repository,
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

if (require.main === module) {
  setVersion().catch(error => {
    console.error(error);
    process.exitCode = 1;
  });
}

module.exports = { createHashFromFile, createNewVersionData, setVersion };
