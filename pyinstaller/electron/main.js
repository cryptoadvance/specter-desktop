// Modules to control application life and create native browser window
const { app, nativeTheme, nativeImage, BrowserWindow, Menu, Tray, screen, shell, dialog, ipcMain } = require('electron')

const path = require('path')
const fs = require('fs')
const { URL } = require('node:url')
const request = require('request')
const https = require('https')
const defaultMenu = require('electron-default-menu')
const { spawn, exec } = require('child_process')
const { appSettingsPath, specterdDirPath, appSettings, platformName, appNameLower } = require('./src/config.js')
const { getFileHash, getAppSettings, versionData, isDev, devFolder, isMac } = require('./src/helpers.js')
const logger = require('./src/logging.js').logger
const downloadloc = require('./downloadloc')
const { downloadSpecterd } = require('./src/download.js')
const getDownloadLocation = downloadloc.getDownloadLocation

// Quit again if there is no version-data in dev
if (isDev && versionData === undefined) {
  console.log(
    `You need to create a version-data.json in your dev folder (${devFolder}) to run the app. Check helpers.js for the format. Quitting ...`
  )
  app.quit()
  return
}

ipcMain.handle('showMessageBoxSync', (e, message, buttons) => {
  dialog.showMessageBoxSync(mainWindow, { message, buttons })
})

if (isDev) {
  logger.info('Running the Electron app in dev mode.')
}

// Register "specter" protocol. This feature is for Mac only as of now.
// This will launch the app for URLs like this: specter://?action=importWallet&data=someData
if (isMac) {
  const isDefaultProtocolClient = app.isDefaultProtocolClient('specter')
  if (!isDefaultProtocolClient) {
    app.setAsDefaultProtocolClient('specter')
  }
}

// Set the dock icon (MacOS and for development only)
if (isMac && isDev) {
  const dockIcon = nativeImage.createFromPath(app.getAppPath() + '/assets-dev/dock_icon_macos.png')
  app.dock.setIcon(dockIcon)
}

let dimensions = { width: 1500, height: 1000 }

// Modify the context menu
const contextMenu = require('electron-context-menu')
const { startSpecterd } = require('./src/specterd.js')
const { showError, initialize } = require('./src/uiHelpers.js')
contextMenu({
  menu: (actions) => [
    {
      label: 'Reload',
      click: () => {
        mainWindow.reload()
      },
    },
    {
      label: 'Back',
      click: () => {
        mainWindow.webContents.goBack()
      },
    },
    actions.separator(),
    actions.copy(),
    actions.cut(),
    actions.paste(),
  ],
})

let specterdProcess
let automaticWalletImport = false
let mainWindow
let prefWindow
let tray
let trayMenu

// Flag the app was quitted
let quitted = false

let webPreferences = {
  worldSafeExecuteJavaScript: true,
  contextIsolation: true,
  preload: path.join(__dirname, 'preload.js'),
}

app.commandLine.appendSwitch('ignore-certificate-errors')

logger.info('Using version ' + appSettings.specterdVersion)
logger.info('Using platformName ' + platformName)

let trySavedAuth = true
app.on('login', function (event, webContents, request, authInfo, callback) {
  event.preventDefault()
  appSettings = getAppSettings() // ensure latest settings are used
  if (appSettings.basicAuth && trySavedAuth) {
    callback(appSettings.basicAuthUser, appSettings.basicAuthPass)
  } else {
    let user = ''
    let pass = ''
    let win = createNewWindow('basic_auth.html', 800, 600, mainWindow, true)
    win.show()
    win.on('close', (event) => {
      win = null
      callback(user, pass)
    })
    ipcMain.once('basic-auth', (event, creds) => {
      if (win != null) {
        user = creds.username
        pass = creds.password
        win.close()
      }
    })
  }
  // if we are prompted for auth again show the auth dialog
  trySavedAuth = false
})

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

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  // Create the tray icon
  logger.info('Framework ready! Starting tray icon ...')
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

  dimensions = screen.getPrimaryDisplay().size

  // create a new `splash`-Window
  logger.info('Framework Ready! Initializing Main-Window, populating Menu ...')
  initMainWindow()

  setMainMenu()
  initialize(mainWindow, tray, trayMenu)

  mainWindow.loadURL(`file://${__dirname}/splash.html`)

  if (!fs.existsSync(specterdDirPath)) {
    logger.info('Creating specterd-binaries folder:' + specterdDirPath)
    fs.mkdirSync(specterdDirPath, { recursive: true })
  }

  if (!appSettings.versionInitialized || appSettings.versionInitialized != versionData.version) {
    logger.info(`Updating ${appSettingsPath} : ${JSON.stringify(appSettings)}`)
    appSettings.specterdVersion = versionData.version
    appSettings.specterdHash = versionData.sha256
    appSettings.versionInitialized = versionData.version
    fs.writeFileSync(appSettingsPath, JSON.stringify(appSettings))
  }
  const specterdPath = specterdDirPath + '/' + appNameLower + 'd'
  if (fs.existsSync(specterdPath + (platformName == 'win64' ? '.exe' : ''))) {
    getFileHash(specterdPath + (platformName == 'win64' ? '.exe' : ''), function (specterdHash) {
      if (appSettings.specterdHash.toLowerCase() == specterdHash || appSettings.specterdHash == '') {
        startSpecterd(specterdPath)
      } else if (appSettings.specterdVersion != '') {
        updatingLoaderMsg('Specterd version could not be validated. Trying again to download the Specter binary ...')
        downloadSpecterd(specterdPath, mainWindow, tray, trayMenu)
      } else {
        updatingLoaderMsg(
          'Specterd file could not be validated and no version is configured in the settings<br>Please go to Preferences and set version to fetch or add an executable manually...'
        )
        updateSpecterdStatus('Failed to locate specterd...')
      }
    })
  } else {
    if (appSettings.specterdVersion) {
      downloadSpecterd(specterdPath, mainWindow, tray, trayMenu)
    } else {
      updatingLoaderMsg(
        'Specterd was not found and no version is configured in the settings<br>Please go to Preferences and set version to fetch or add an executable manually...'
      )
      updateSpecterdStatus('Failed to locate specterd...')
    }
  }
})

function initMainWindow() {
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

  mainWindow.on('close', function (event) {
    if (platformName == 'win64') {
      quitSpecterd()
      app.quit()
    } else {
      event.preventDefault()
      mainWindow.hide()
    }
  })

  mainWindow.webContents.on('did-fail-load', function () {
    mainWindow.loadURL(`file://${__dirname}/splash.html`)
    updatingLoaderMsg(
      `Failed to load: ${appSettings.specterURL}<br>Please make sure the URL is entered correctly in the settings and try again...</b>`
    )
  })
}

app.on('window-all-closed', function () {
  if (platformName == 'win64') {
    quitSpecterd()
    app.quit()
  }
})

// Cleanup before quitting (helps prevent memory leaks)
app.on('before-quit', (event) => {
  if (!quitted) {
    logger.info('Quitting ...')
    quitted = true
    quitSpecterd()
    if (mainWindow && !mainWindow.isDestroyed()) {
      if (progressBar) {
        // You can only destroy the progress bar if it hadn't been closed before
        if (progressBar.browserWindow) {
          progressBar.destroy()
        }
        progressBar = null
      }
      mainWindow.destroy()
      mainWindow = null
      prefWindow = null
      tray = null
    }
  }
})

ipcMain.on('request-mainprocess-action', (event, arg) => {
  switch (arg.message) {
    case 'save-preferences':
      // Child process already closed
      if (!specterdProcess || specterdProcess.exitCode != null) {
        prefWindow.webContents.executeJavaScript(`savePreferences()`)
      } else {
        specterdProcess.on('close', (code) => {
          logger.info(`child process exited with code ${code}`)
          prefWindow.webContents.executeJavaScript(`savePreferences()`)
        })
        quitSpecterd()
      }
      break
    case 'quit-app':
      quitSpecterd()
      app.quit()
      break
  }
})

function quitSpecterd() {
  if (specterdProcess) {
    try {
      if (platformName == 'win64') {
        exec('taskkill /F /T /PID ' + specterdProcess.pid)
        exec('taskkill /IM specterd.exe ')
        process.kill(-specterdProcess.pid)
      }
      specterdProcess.kill('SIGINT')
    } catch (e) {
      logger.info('Specterd quit warning: ' + e)
    }
  }
}

function setMainMenu() {
  const menu = defaultMenu(app, shell)

  // Add custom menu
  if (platformName == 'osx') {
    menu[0].submenu.splice(1, 0, {
      label: 'Settings...', // This is a naming convention on MacOS. If you use just "Preferences", it gets translated to "Settings..." on MacOS.
      click: openPreferences,
      accelerator: 'CmdOrCtrl+,',
    })
    menu[0].submenu.splice(1, 0, {
      label: 'Specter Logs',
      click: openErrorLog,
      accelerator: 'CmdOrCtrl+L',
    })
  } else {
    menu.unshift({
      label: 'Specter',
      submenu: [
        {
          label: 'Settings',
          click: openPreferences,
          accelerator: 'CmdOrCtrl+,',
        },
        {
          label: 'Specter Logs',
          click: openErrorLog,
          accelerator: 'CmdOrCtrl+L',
        },
      ],
    })
  }

  Menu.setApplicationMenu(Menu.buildFromTemplate(menu))
}

function createNewWindow(htmlContentFile, width, height, parent, modal) {
  if (!width) {
    width = 700
  }
  if (!height) {
    height = 750
  }
  if (!parent) {
    parent = null
  }
  if (!modal) {
    modal = false
  }
  prefWindow = new BrowserWindow({
    width: width,
    height: height,
    parent: parent,
    modal: modal,
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false, // acceptable as this is not the mainwindow. No remote content!
      enableRemoteModule: true,
    },
  })
  prefWindow.webContents.on('new-window', function (e, url) {
    e.preventDefault()
    shell.openExternal(url)
  })
  prefWindow.loadURL(`file://${__dirname}/${htmlContentFile}`)
  return prefWindow
}

function openPreferences() {
  createNewWindow('settings.html', 800, 750, mainWindow).show()
}

function openErrorLog() {
  ;(width = parseInt(dimensions.width * 0.7)), (height = parseInt(dimensions.height * 0.7))
  createNewWindow('error_logs.html', width, height).show()
}

process.on('unhandledRejection', (error) => {
  showError(error)
  logger.error(error.toString(), error.name)
})

process.on('uncaughtException', (error) => {
  showError(error, mainWindow)
  // I would love to rethrow the error here as this would create a stacktrace in the logs
  // but this will terminate the whole process even though i've set
  // exitOnError: false in the winstonOptions above.
  // Unacceptable for the folks which can't use a commandline, clicking an icon
  //throw(error)
  logger.error(error.stack)
})
