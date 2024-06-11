const path = require('path')
const { Menu, BrowserWindow, nativeTheme, app, Tray, nativeImage } = require('electron')
const { logger } = require('./logging')
const { appSettings, isDev, platformName } = require('./config')
const ProgressBar = require('electron-progressbar')
const { isMac } = require('./helpers')
const { shell } = require('electron')

// Initialized with initMainWindow
let mainWindow
// Initialized with InitTray
let tray
let trayMenu

const loadUrl = (url) => {
  mainWindow.loadURL(url)
}

const executeJavaScript = (code) => {
  mainWindow.webContents.executeJavaScript(code)
}

function showError(error) {
  updatingLoaderMsg('Specter encountered an error:' + error.toString())
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

let webPreferences = {
  // worldSafeExecuteJavaScript: true, Removed in Electron 14
  contextIsolation: true,
  preload: path.join(__dirname, 'preload.js'),
}

function initMainWindow(dimensions) {
  // In production we use the icons from the build folder
  // Note: On MacOS setting an icon here as no effect
  const iconPath = isDev ? path.join(__dirname, 'assets-dev/app_icon.png') : ''
  mainWindow = new BrowserWindow({
    width: parseInt(dimensions.width * 0.8),
    minWidth: 1120,
    height: parseInt(dimensions.height * 0.8),
    icon: iconPath,
    webPreferences,
  })

  // Ensures that any links with target="_blank" or window.open() will be opened in the user's default browser instead of within the app
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.webContents.on('did-fail-load', function () {
    mainWindow.loadURL(`file://${__dirname}/splash.html`)
    updatingLoaderMsg(
      `Failed to load: ${appSettings.specterURL}<br>Please make sure the URL is entered correctly in the settings and try again...</b>`
    )
  })
  return mainWindow
}

const initTray = (openPreferences, quitSpecterd) => {
  if (isMac) {
    const trayIconPath = nativeTheme.shouldUseDarkColors ? '/assets/menu_icon_dark.png' : '/assets/menu_icon_light.png'
    const createTrayIcon = (trayIconPath) => {
      let trayIcon = nativeImage.createFromPath(app.getAppPath() + trayIconPath)
      // Resize
      trayIcon = trayIcon.resize({ width: 22, height: 22 })
      return trayIcon
    }
    const trayIcon = createTrayIcon(trayIconPath)
    tray = new Tray(trayIcon)

    // Change the tray icon if appearance is changed in Mac settings
    const updateTrayIcon = () => {
      logger.info('Updating tray icon ...')
      const trayIconPath = nativeTheme.shouldUseDarkColors ? '/assets/menu_icon_dark.png' : '/assets/menu_icon_light.png'
      const newTrayIcon = createTrayIcon(trayIconPath)
      tray.setImage(newTrayIcon)
    }
    nativeTheme.on('updated', updateTrayIcon)
  } else {
    const trayIcon = nativeImage.createFromPath(app.getAppPath() + '/assets/menu_icon.png')
    tray = new Tray(trayIcon)
  }

  trayMenu = [
    { label: 'Launching Specter ...', enabled: false },
    {
      label: 'Show Specter',
      click() {
        mainWindow.show()
      },
    },
    {
      label: 'Settings',
      click() {
        openPreferences()
      },
    },
    {
      label: 'Quit',
      click() {
        quitSpecterd()
        app.quit()
      },
    },
  ]
  tray.setToolTip('Specter')
  tray.setContextMenu(Menu.buildFromTemplate(trayMenu))
}

const createProgressBar = (totalBytes) => {
  progressBar = new ProgressBar({
    indeterminate: false,
    abortOnError: true,
    text: 'Downloading the Specter binary from GitHub',
    detail:
      'This can take several minutes depending on your Internet connection. Specter will start once the download is finished.',
    maxValue: totalBytes,
    browserWindow: {
      parent: mainWindow,
    },
    style: {
      detail: {
        'margin-bottom': '12px',
      },
      bar: {
        'background-color': '#fff',
      },
      value: {
        'background-color': '#000',
      },
    },
  })
  return progressBar
}

module.exports = {
  loadUrl,
  executeJavaScript,
  showError,
  updatingLoaderMsg,
  updateSpecterdStatus,
  createWindow,
  initMainWindow,
  mainWindow,
  initTray,
  createProgressBar,
}
