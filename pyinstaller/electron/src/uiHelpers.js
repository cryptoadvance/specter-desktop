const { Menu } = require('electron')
const { logger } = require('./logging')
const { appSettings } = require('./config')

let mainWindow
let tray
let trayMenu

const initialize = (myMainWindow, myTray, myTrayMenu) => {
  mainWindow = myMainWindow
  tray = myTray
  trayMenu = myTrayMenu
}

function showError(error) {
  updatingLoaderMsg('Specter encountered an error:' + error.toString(), mainWindow)
}

function updatingLoaderMsg(msg, showSpinner = false) {
  if (mainWindow) {
    // see preload.js where this is setup
    mainWindow.webContents.send('update-loader-message', {
      msg,
      showSpinner,
    })
  } else {
    logger.error('mainWindow not initialized in updatingLoaderMsg')
  }
  logger.info('Updated LoaderMsg: ' + msg)
}

function updateSpecterdStatus(status) {
  trayMenu[0] = { label: status, enabled: false }
  tray.setContextMenu(Menu.buildFromTemplate(trayMenu))
}

function createWindow(specterURL) {
  if (!mainWindow) {
    initMainWindow()
  }

  // Create the browser window.
  if (appSettings.tor) {
    mainWindow.webContents.session.setProxy({ proxyRules: appSettings.proxyURL })
  }
  mainWindow.loadURL(specterURL + '?mode=remote')
}

module.exports = {
  initialize,
  showError,
  updatingLoaderMsg,
  updateSpecterdStatus,
  createWindow,
}
