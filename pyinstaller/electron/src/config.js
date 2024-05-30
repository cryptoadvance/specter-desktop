const os = require('os')
const path = require('path')
const fs = require('fs')


const downloadloc = require('../downloadloc');



let platformName = ''
switch (process.platform) {
  case 'darwin':
    platformName = 'osx'
    break
  case 'win32':
    platformName = 'win64'
    break
  case 'linux':
    platformName = 'x86_64-linux-gnu'
    break
  default:
    throw `Unknown platformName ${platformName}`
}
const appName = downloadloc.appName()
const appNameLower = appName.toLowerCase()
const isDev = process.env.NODE_ENV === "development"
const unresolvedDevFolder = process.env.SPECTER_DATA_FOLDER || "~/.specter_dev"
const devFolder = unresolvedDevFolder.replace(/^~/, os.homedir());
const prodFolder = path.resolve(os.homedir(), `.${appNameLower}`)
let appSettingsPath
let appSettings
let specterdDirPath
let specterAppLogPath
let versionDataPath
let versionData

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
    specterdHash: (versionData && versionData.sha256 !== undefined) ? versionData.sha256[process.arch] : 'unknown',
    specterdCLIArgs: "",
    versionInitialized: false
  }

  try {
    if (!fs.existsSync(appSettingsPath)){
        fs.mkdirSync(path.resolve(appSettingsPath, '..'), { recursive: true });
    }
    fs.writeFileSync(appSettingsPath, JSON.stringify(defaultSettings), { flag: 'wx' });
  } catch (error) {
    if (error.toString().startsWith("Error: EEXIST: file already exists,")) {
      //ignore
    } else {
      throw error
    } 
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

if (isDev) {
    versionDataPath = `${devFolder}/version-data.json`

} else {
    versionDataPath = `../version-data.json`
}
versionData = require(versionDataPath)

  
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
appSettings = getAppSettings()

module.exports = {
    platformName,
    appSettings,
    appName,
    appNameLower,
    appSettingsPath,
    specterdDirPath,
    specterAppLogPath,
    versionDataPath,
    versionData,
    getAppSettings,
    isDev: isDev,
    devFolder,
}