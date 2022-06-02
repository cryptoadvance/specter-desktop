const fs = require('fs')
const path = require('path')
const crypto = require('crypto')
const readLastLines = require('read-last-lines');
const downloadloc = require('./downloadloc');
const { loggers } = require('winston');
const appName = downloadloc.appName()
const appNameLower = appName.toLowerCase()

let versionData
try {
    versionData = require('./version-data.json')
    console.log(versionData)
} catch (e) {
    console.log('Could not find default version data configurations...'+e)
    versionData = {
        "version": "",
        "sha256": ""
    }
}
const appSettingsPath = path.resolve(require('os').homedir(), `.${appNameLower}/app_settings.json`)
const specterdDirPath = path.resolve(require('os').homedir(), `.${appNameLower}/specterd-binaries`)
const specterAppLogPath = path.resolve(require('os').homedir(), `.${appNameLower}/specterApp.log`)

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
      basicAuth: false,
      basicAuthUser: '',
      basicAuthPass: '',
      tor: false,
      proxyURL: "socks5://127.0.0.1:9050",
      specterdVersion: versionData.version,
      specterdHash: versionData.sha256,
      specterdCLIArgs: "",
      versionInitialized: false
    }
  
    try {
      if (!fs.existsSync(appSettingsPath)){
          fs.mkdirSync(path.resolve(appSettingsPath, '..'), { recursive: true });
      }
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

function getSpecterAppLogs(callback) {  
  readLastLines.read(specterAppLogPath, 700)
	.then(callback);
}

module.exports = {
    getFileHash: getFileHash,
    appSettingsPath: appSettingsPath,
    getAppSettings: getAppSettings,
    specterdDirPath: specterdDirPath,
    getSpecterAppLogs: getSpecterAppLogs,
    specterAppLogPath: specterAppLogPath
}
