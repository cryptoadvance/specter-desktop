const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

let versionData
try {
    versionData = require('./version-data.json')
} catch {
    console.log('Could not find default version data configurations...')
    versionData = {
        "version": "",
        "sha256": ""
    }
}
const appSettingsPath = path.resolve(require('os').homedir(), '.specter/app_settings.json')
const specterdDirPath = path.resolve(require('os').homedir(), '.specter/specterd-binaries')

function getFileHash(filename, callback) {
  let shasum = crypto.createHash('sha256')
  // Updating shasum with file content
  , s = fs.ReadStream(filename)
  s.on('data', function(data) {
    shasum.update(data)
  })
  // making digest
  s.on('end', function() {
  var hash = shasum.digest('hex')
    callback(hash)
  })
}

function getAppSettings() {  
    let defaultSettings = {
      mode: 'specterd',
      specterURL: 'http://localhost:25441',
      tor: false,
      proxyURL: "socks5://127.0.0.1:9050",
      specterdVersion: versionData.version,
      specterdHash: versionData.sha256,
      specterdCLIArgs: ""
    }
  
    try {
      fs.writeFileSync(appSettingsPath, JSON.stringify(defaultSettings), { flag: 'wx' });
    } catch {
        // settings file already exists
    }
  
    // Make sure to add missing settings in case the format changed or new settings were added
    let appSettings = require(appSettingsPath)
    for (let key of Object.keys(defaultSettings)) {
      if (!appSettings.hasOwnProperty(key)) {
        appSettings[key] = defaultSettings[key]
      }
    }
  
    return appSettings
  }

module.exports = {
    getFileHash: getFileHash,
    appSettingsPath: appSettingsPath,
    getAppSettings: getAppSettings,
    specterdDirPath: specterdDirPath
}
