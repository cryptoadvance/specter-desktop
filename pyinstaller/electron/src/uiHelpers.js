const { Menu } = require('electron')
const { logger } = require('./logging')

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
    logger.info('---------------------' + msg)
    mainWindow.webContents.send('update-loader-message', {
      msg,
      showSpinner,
    })
  }
  logger.info('Updated LoaderMsg: ' + msg)
}

function updateSpecterdStatus(status) {
  trayMenu[0] = { label: status, enabled: false }
  tray.setContextMenu(Menu.buildFromTemplate(trayMenu))
}

module.exports = {
  initialize,
  showError,
  updatingLoaderMsg,
  updateSpecterdStatus,
}
