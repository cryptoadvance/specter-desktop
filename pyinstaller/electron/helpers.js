const fs = require('fs')
const os = require('os')
const path = require('path')
const crypto = require('crypto')
const readLastLines = require('read-last-lines');
const downloadloc = require('./downloadloc');
const appName = downloadloc.appName()
const appNameLower = appName.toLowerCase()
const isDev = process.env.NODE_ENV === "development"
const unresolvedDevFolder = process.env.SPECTER_DATA_FOLDER || "~/.specter_dev"
const devFolder = unresolvedDevFolder.replace(/^~/, os.homedir());
const prodFolder = path.resolve(os.homedir(), `.${appNameLower}`)
const isMac = process.platform === 'darwin'

let appSettingsPath
let specterdDirPath
let specterAppLogPath
let versionData

// Use different version-data.jsons

// Should look like this: 
// {
//   "version": "v2.0.0-pre32",
//   "sha256": "aa049abf3e75199bad26fbded08ee5911ad48e325b42c43ec195136bd0736785"
// }

if (isDev) {
  let versionDataPath = `${devFolder}/version-data.json`
  try {
    versionData = require(versionDataPath)
  }
  catch {
  }
}
else {
  try {
    versionData = require('./version-data.json')
    } 
  catch (e) {
    console.log('Could not find default version data configurations: '+e)
    versionData = {
        "version": "",
        "sha256": ""
    }
  }
}

if (isDev) {
  appSettingsPath = `${devFolder}/app_settings.json`
  specterdDirPath = `${devFolder}/specterd-binaries` 
  specterAppLogPath = `${devFolder}/specterApp.log`
}
else {
  appSettingsPath = `${prodFolder}/app_settings.json`
  specterdDirPath = `${prodFolder}/specterd-binaries` 
  specterAppLogPath = `${prodFolder}/specterApp.log`
}

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
      specterdVersion: (versionData && versionData.version !== undefined) ? versionData.version : 'unknown',
      specterdHash: (versionData && versionData.sha256 !== undefined) ? versionData.sha256 : 'unknown',
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
    specterAppLogPath: specterAppLogPath,
    versionData,
    isDev: isDev,
    devFolder,
    isMac, isMac
}
