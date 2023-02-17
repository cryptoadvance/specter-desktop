// Modules to control application life and create native browser window
const { app, nativeTheme, nativeImage, BrowserWindow, Menu, Tray, screen, shell, dialog, ipcMain } = require('electron')

const path = require('path')
const fs = require('fs')
const request = require('request')
const extract = require('extract-zip')
const defaultMenu = require('electron-default-menu');
const { spawn, exec } = require('child_process');

const helpers = require('./helpers')
const getFileHash = helpers.getFileHash
const getAppSettings = helpers.getAppSettings
const appSettingsPath = helpers.appSettingsPath
const specterdDirPath = helpers.specterdDirPath

const downloadloc = require('./downloadloc')
const getDownloadLocation = downloadloc.getDownloadLocation
const appName = downloadloc.appName()
const appNameLower = appName.toLowerCase()

ipcMain.handle("showMessageBoxSync", (e, message, buttons) => {
    dialog.showMessageBoxSync(mainWindow, { message, buttons });
});

// Helper
const isMac = process.platform === 'darwin'
const isDev = process.env.NODE_ENV !== "production"

// Logging
const {transports, format, createLogger } = require('winston')
const combinedLog = new transports.File({ filename: helpers.specterAppLogPath });
const winstonOptions = {
    exitOnError: false,
    format: format.combine(
      format.timestamp(),
      // format.timestamp({format:'MM/DD/YYYY hh:mm:ss.SSS'}),
      format.json(),
      format.printf(info => {
        return `${info.timestamp} [${info.level}] : ${info.message}`;
      })
    ),
    transports: [
      new transports.Console({json:false}),
      combinedLog
    ],
    exceptionHandlers: [
      combinedLog
    ]
}
const logger = createLogger(winstonOptions)

if (isDev) {
  logger.info('Running the Electron app in dev mode.')
}

logger.info(process.env)
let appSettings = getAppSettings()

let dimensions = { widIth: 1500, height: 1000 };

const contextMenu = require('electron-context-menu');
const { options } = require('request')

// Set the dock icon (MacOS and for development only)
if (isMac && isDev) {
  const dockIcon = nativeImage.createFromPath(
    app.getAppPath() + "/assets-dev/dock_icon_macos.png"
  );
  app.dock.setIcon(dockIcon)
}

contextMenu({
	menu: (actions) => [
		{
      label: 'Reload',
      click: () => {
        mainWindow.reload()
      }
    },
    {
      label: 'Back',
      click: () => {
        mainWindow.webContents.goBack()
      }
    },
    actions.separator(),
    actions.copy(),
    actions.cut(),
    actions.paste()
	]
});

const download = (uri, filename, callback) => {
    request.head(uri, (err, res, body) => {
        logger.info('content-type:', res.headers['content-type'])
        logger.info('content-length:', res.headers['content-length'])
        if (res.statusCode != 404) {
          request(uri).pipe(fs.createWriteStream(filename)).on('close', callback)
        } else {
          callback(true)
        }
    })
}

let specterdProcess
let mainWindow
let prefWindow
let tray
let trayMenu

// Flag the app was quitted
let quitted = false

let webPreferences = {
  worldSafeExecuteJavaScript: true,
  contextIsolation: true,
  preload: path.join(__dirname, 'preload.js')
}

app.commandLine.appendSwitch('ignore-certificate-errors');

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
logger.info("Using version " + appSettings.specterdVersion);
logger.info("Using platformName " + platformName);

let trySavedAuth = true
app.on('login', function(event, webContents, request, authInfo, callback) {
  event.preventDefault();
  appSettings = getAppSettings(); // ensure latest settings are used
  if (appSettings.basicAuth && trySavedAuth) {
    callback(appSettings.basicAuthUser, appSettings.basicAuthPass);
  } else {
    let user = '';
    let pass = '';
    let win = createNewWindow('basic_auth.html', 800, 600, mainWindow, true);
    win.show();
    win.on('close', (event) => {
      win = null;
      callback(user, pass);
    });
    ipcMain.once('basic-auth', (event, creds) => {
      if (win != null) {
        user = creds.username;
        pass = creds.password;
        win.close();
      }
    });
  }
  // if we are prompted for auth again show the auth dialog
  trySavedAuth = false;
})

function createWindow (specterURL) {  
  if (!mainWindow) {
    initMainWindow()
  }

  // Create the browser window.
  if (appSettings.tor) {
    mainWindow.webContents.session.setProxy({ proxyRules: appSettings.proxyURL });
  }

  mainWindow.loadURL(specterURL + '?mode=remote')
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  // Create the tray icon
  logger.info("Framework ready! Starting tray icon ...");
  if (isMac) {
    const trayIconPath = nativeTheme.shouldUseDarkColors
      ? "/assets/menu_icon_dark.png"
      : "/assets/menu_icon_light.png";
    const createTrayIcon = (trayIconPath) => {
      let trayIcon = nativeImage.createFromPath(
        app.getAppPath() + trayIconPath
      );
      // Resize
      trayIcon = trayIcon.resize({ width: 22, height: 22 });
      return trayIcon
    }
    const trayIcon = createTrayIcon(trayIconPath)
    tray = new Tray(trayIcon);

    // Change the tray icon if appearance is changed in Mac settings 
    const updateTrayIcon = () => {
      logger.info('Updating tray icon ...')
      const trayIconPath = nativeTheme.shouldUseDarkColors
        ? "/assets/menu_icon_dark.png"
        : "/assets/menu_icon_light.png";
      const newTrayIcon = createTrayIcon(trayIconPath)
      tray.setImage(newTrayIcon);
    }
    nativeTheme.on('updated', updateTrayIcon)
  }
  else {
    const trayIcon = nativeImage.createFromPath(
      app.getAppPath() + "/assets/menu_icon.png"
    );
    tray = new Tray(trayIcon)
  }

  trayMenu = [
    { label: 'Launching Specter ...', enabled: false },
    { label: 'Show Specter',  click() { mainWindow.show() }},
    { label: 'Preferences',  click() { openPreferences() }},
    { label: 'Quit',  click() { quitSpecterd(); app.quit() } },
  ]
  tray.setToolTip('Specter')
  tray.setContextMenu(Menu.buildFromTemplate(trayMenu))

  dimensions = screen.getPrimaryDisplay().size;

  // create a new `splash`-Window 
  logger.info("Framework Ready! Initializing Main-Window, populating Menu ...");
  initMainWindow()

  setMainMenu();
  
  mainWindow.loadURL(`file://${__dirname}/splash.html`);

  if (!fs.existsSync(specterdDirPath)){
    logger.info("Creating specterd-binaries folder");
    fs.mkdirSync(specterdDirPath, { recursive: true });
  }

  let versionData = require('./version-data.json')
  if (!appSettings.versionInitialized || appSettings.versionInitialized != versionData.version) {
    logger.info(`Updating ${appSettingsPath} : ${JSON.stringify(appSettings)}`);
    appSettings.specterdVersion = versionData.version
    appSettings.specterdHash = versionData.sha256
    appSettings.versionInitialized = versionData.version
    fs.writeFileSync(appSettingsPath, JSON.stringify(appSettings))
  }
  const specterdPath = specterdDirPath + '/' + appNameLower + 'd'
  if (fs.existsSync(specterdPath + (platformName == 'win64' ? '.exe' : ''))) {
    getFileHash(specterdPath + (platformName == 'win64' ? '.exe' : ''), function (specterdHash) {
      if (appSettings.specterdHash.toLowerCase() == specterdHash || appSettings.specterdHash == "") {
        
        startSpecterd(specterdPath)
      } else if (appSettings.specterdVersion != "") {
        updatingLoaderMsg('Specterd version could not be validated. Retrying fetching specterd...')
        updateSpecterdStatus('Fetching Specter binary...')
        downloadSpecterd(specterdPath)
      } else {
        updatingLoaderMsg('Specterd file could not be validated and no version is configured in the settings<br>Please go to Preferences and set version to fetch or add an executable manually...')
        updateSpecterdStatus('Failed to locate specterd...')
      }
    })
  } else {
    if (appSettings.specterdVersion) {
      downloadSpecterd(specterdPath)
    } else {
      updatingLoaderMsg('Specterd was not found and no version is configured in the settings<br>Please go to Preferences and set version to fetch or add an executable manually...')
      updateSpecterdStatus('Failed to locate specterd...')
    }
  }
})

function initMainWindow() {
  // In production we use the icons from the build folder
  // Note: On MacOS setting an icon here as no effect
  const iconPath = isDev ? path.join(__dirname, 'assets-dev/app_icon.png') : ""
  mainWindow = new BrowserWindow({
    width: parseInt(dimensions.width * 0.8),
    height: parseInt(dimensions.height * 0.8),
    icon: iconPath,
    webPreferences
  })
  
  mainWindow.webContents.on('new-window', function(e, url) {
    e.preventDefault();
    shell.openExternal(url);
  });

  mainWindow.on('close', function (event) {
      if(platformName == 'win64') {
        quitSpecterd()
        app.quit()
      } else {
        event.preventDefault();
        mainWindow.hide();
      }
  });

  mainWindow.webContents.on("did-fail-load", function() {
    mainWindow.loadURL(`file://${__dirname}/splash.html`);
    updatingLoaderMsg(`Failed to load: ${appSettings.specterURL}<br>Please make sure the URL is entered correctly in the Preferences and try again...`)
  });
}

function downloadSpecterd(specterdPath) {
  updatingLoaderMsg(`Fetching the ${appName} binary.<br>This might take a minute...`)
  updateSpecterdStatus(`Fetching ${appName} binary...`)
  logger.info("Using version " + appSettings.specterdVersion);
  logger.info("Using platformName " + platformName);
  
  download_location = getDownloadLocation(appSettings.specterdVersion, platformName)
  logger.info("Downloading from "+download_location);
  download(download_location, specterdPath + '.zip', function(errored) {
    if (errored == true) {
      updatingLoaderMsg(`Fetching ${appNameLower} binary from the server failed, could not reach the server or the file could not have been found.`)
      updateSpecterdStatus(`Fetching ${appNameLower}d failed...`)
      return
    }

    updatingLoaderMsg('Unpacking files...')
    logger.info("Extracting "+specterdPath);

    extract(specterdPath + '.zip', { dir: specterdPath + '-dir' }).then(function () {
      let extraPath = ''
      switch (process.platform) {
        case 'darwin':
          extraPath = appNameLower + "d"
          break
        case 'win32':
          extraPath = appNameLower + 'd.exe'
          break
        case 'linux':
          extraPath = appNameLower + 'd'
      }
      var oldPath = specterdPath + `-dir/${extraPath}`
      var newPath = specterdPath + (platformName == 'win64' ? '.exe' : '')

      fs.renameSync(oldPath, newPath)
      updatingLoaderMsg('Cleaning up...')
      fs.unlinkSync(specterdPath + '.zip')
      fs.rmdirSync(specterdPath + '-dir', { recursive: true });
      getFileHash(specterdPath + (platformName == 'win64' ? '.exe' : ''), function(specterdHash) {
        if (appSettings.specterdHash.toLowerCase() === specterdHash || appSettings.specterdHash == "") {
          startSpecterd(specterdPath)
        } else {
          updatingLoaderMsg('Specterd version could not be validated.')
          logger.error(`hash of downloaded file: ${specterdHash}`)
          logger.error(`Expected hash: ${appSettings.specterdHash}`)
          updateSpecterdStatus('Failed to launch specterd...')

          // app.quit()
          // TODO: This should never happen unless the specterd file was swapped on GitHub.
          // Think of what would be the appropriate way to handle this...
        }
      })
    })
  })
}

function updateSpecterdStatus(status) {
  trayMenu[0] = { label: status, enabled: false };
  tray.setContextMenu(Menu.buildFromTemplate(trayMenu))
}

function updatingLoaderMsg(msg, showSpinner=false) {
  if (mainWindow) {
    let code = `
    var launchText = document.getElementById('launch-text');
    if (launchText) {
      launchText.innerHTML = '${msg}';
    }
    var spinnerElement = document.getElementById('spinner');
    if (spinnerElement) {
      if (${showSpinner} === true) {
        spinnerElement.classList.remove('hidden')
      }
      else {
        spinnerElement.classList.add('hidden')
      }
    }
    `;
    mainWindow.webContents.executeJavaScript(code);
  } 
  logger.info("Updated LoaderMsg: "+msg)
}

function checkSpecterd(logs, specterdStarted) {
  // There doesn't seem to be another more straightforward way to check whether specterd is running: https://github.com/nodejs/help/issues/1191
  // Setting a timeout to avoid waiting for specterd endlessly
  const timeout = 180000 // 3 minutes
  const now = Date.now()
  const timeElapsed = now - specterdStarted
  if (timeElapsed > timeout) {
    return "timeout"
  }
  if (logs.toString().includes('Serving Flask app')) {
    return 'running';
  }
  else {
    return 'not running'
  }
}

function startSpecterd(specterdPath) {
  if (platformName == 'win64') {
    specterdPath += '.exe'
  }
  let appSettings = getAppSettings()
  let hwiBridgeMode = appSettings.mode == 'hwibridge'
  updatingLoaderMsg('Launching Specter ...', showSpinner=true)
  updateSpecterdStatus('Launching Specter ...')
  let specterdArgs = ["server"]
  specterdArgs.push("--no-filelog")
  if (hwiBridgeMode) specterdArgs.push('--hwibridge')
  if (appSettings.specterdCLIArgs != '') {
    if (specterdArgs == null) {
      specterdArgs = []
    }
    let specterdExtraArgs = appSettings.specterdCLIArgs.split(' ')
    specterdExtraArgs.forEach((arg, index) => specterdExtraArgs[index] = arg.trim())
    specterdArgs = specterdArgs.concat(specterdExtraArgs)
  }


  logger.info(`Starting specterd ${specterdPath} ${specterdArgs}`);
  // locale fix (copying from nodejs-env + adding locales)
  const options = {
    env: { ...process.env}
  }
  options.env['LC_ALL']='en_US.utf-8'
  options.env['LANG'] = 'en_US.utf-8'
  options.env['SPECTER_LOGFORMAT'] = 'SPECTERD: %(levelname)s in %(module)s: %(message)s'
  specterdProcess = spawn(specterdPath, specterdArgs, options);
  const specterdStarted = Date.now()
  
  // We are checking for both, stdout and stderr, to be on the save side.
  let specterIsRunning = false
  specterdProcess.stdout.on('data', (data) => {
    logger.info("stdout-"+data.toString())
    let serverdStatus = checkSpecterd(data, specterdStarted)
    // We don't want to check the logs forever, just until specterd is up and running
    if (!specterIsRunning) {
      if(serverdStatus === 'running') {
        logger.info(`Specter server seems to run ...`);
        updateSpecterdStatus('Specter is running')
        specterIsRunning = true
        if (mainWindow) {
          logger.info('... creating Electron window for it.')
          createWindow(appSettings.specterURL)
        }
      }
      else if(serverdStatus === 'timeout')  {
        showError('Specter does not seem to start. Check the logs in the menu for more details.')
        updateSpecterdStatus('Specter does not start')
        logger.error('Startup timeout for specterd exceeded')
      }
      else {
        updatingLoaderMsg('Still waiting for Specter to start ...')
        updateSpecterdStatus('Specter is starting')
      }
    }
  });

  specterdProcess.stderr.on('data', (data) => {
    logger.info("stderr-"+data.toString())
    let serverdStatus = checkSpecterd(data, specterdStarted)
    if (!specterIsRunning) {
      if(serverdStatus === 'running') {
        logger.info(`Specter server seems to run ...`);
        updateSpecterdStatus('Specter is running')
        specterIsRunning = true
        if (mainWindow) {
          logger.info('... creating Electron window for it.')
          createWindow(appSettings.specterURL)
        }
      }
      else if(serverdStatus === 'timeout')  {
        showError('Specter does not seem to start. Check the logs in the menu for more details.')
        updateSpecterdStatus('Specter does not start')
        logger.error('Startup timeout for specterd exceeded')
      }
      else {
        updatingLoaderMsg('Still waiting for Specter to start ...')
        updateSpecterdStatus('Specter is starting')
      }
    }
  });

  specterdProcess.on('exit', (code) => {
    logger.error(`specterd exited with code ${code}`);
    showError(`Specter exited with exit code ${code}. Check the logs in the menu for more details.`)
  });

  specterdProcess.on('error', (err) => {
    logger.error(`Error starting Specter server: ${err}`);
    showError(`Specter failed to start, due to ${err.message}. Check the logs in the menu for more details.`)
  });

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow(appSettings.specterURL)
  })
  // since these are streams, you can pipe them elsewhere
  specterdProcess.on('close', (code) => {
    updateSpecterdStatus('Specter stopped...')
    logger.info(`child process exited with code ${code}`);
  });
}

app.on('window-all-closed', function(){
  if(platformName == 'win64') {
    quitSpecterd()
    app.quit()
  }
});

app.on('before-quit', () => {
  if (!quitted) {
    quitted = true
    quitSpecterd()
  
    if (mainWindow && !mainWindow.isDestroyed()) {
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
        prefWindow.webContents.executeJavaScript(`savePreferences()`);
      } else {
        specterdProcess.on('close', (code) => {
          logger.info(`child process exited with code ${code}`);
          prefWindow.webContents.executeJavaScript(`savePreferences()`);
        });
        quitSpecterd()
      }
      break
    case 'quit-app':
      quitSpecterd()
      app.quit()
      break
  }
});

function quitSpecterd() {
  if (specterdProcess) {
    try {
      if (platformName == 'win64') {
        exec('taskkill /F /T /PID ' + specterdProcess.pid);
        exec('taskkill /IM specterd.exe ');
        process.kill(-specterdProcess.pid)
      }
      specterdProcess.kill('SIGINT')
    } catch (e) {
      logger.info('Specterd quit warning: ' + e)
    }
  }
}

function setMainMenu() {
  const menu = defaultMenu(app, shell);

  // Add custom menu
  if (platformName == 'osx') {
    menu[0].submenu.splice(1, 0,
      {
        label: 'Preferences',
        click: openPreferences,
        accelerator: "CmdOrCtrl+,"
      }
    );
    menu[0].submenu.splice(1, 0,
      {
        label: 'Specter Logs',
        click: openErrorLog,
        accelerator: "CmdOrCtrl+,"
      }
    );
  } else {
    menu.unshift({
        label: 'Specter',
        submenu: [
        {
          label: 'Preferences',
          click: openPreferences,
          accelerator: "CmdOrCtrl+,"
        },
        {
          label: 'Specter Logs',
          click: openErrorLog,
          accelerator: "CmdOrCtrl+,"
        }
        ]
      } 
    );
  }
  
  Menu.setApplicationMenu(Menu.buildFromTemplate(menu));
}


function createNewWindow(htmlContentFile, width, height, parent, modal) {
  if (! width) {width=700}
  if (! height) {height=750}
  if (! parent) {parent=null}
  if (! modal) {modal=false}
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
      
    }
  })
  prefWindow.webContents.on('new-window', function(e, url) {
    e.preventDefault();
    shell.openExternal(url);
  });
  prefWindow.loadURL(`file://${__dirname}/${htmlContentFile}`)
  return prefWindow
}


function openPreferences() {
  createNewWindow("settings.html", 800, 750, mainWindow).show()
}

function openErrorLog() {
  width = parseInt(dimensions.width * 0.7),
  height = parseInt(dimensions.height * 0.7)
  createNewWindow("error_logs.html", width, height).show()
}

function showError(error) {
  updatingLoaderMsg('Specter encountered an error:<br>' + error.toString())
}

process.on('unhandledRejection', error => {
  showError(error)
  logger.error(error.toString(), error.name)
})

process.on("uncaughtException", error => {
  showError(error)
  // I would love to rethrow the error here as this would create a stacktrace in the logs
  // but this will terminate the whole process even though i've set
  // exitOnError: false in the wistonOptions above.
  // Unacceptable for the folks which can't use a commandline, clicking an icon
  //throw(error)
  logger.error(error.toString())
})
