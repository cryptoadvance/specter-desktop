// Modules to control application life and create native browser window
const { app, BrowserWindow, Menu, Tray, screen, shell, dialog, ipcMain } = require('electron')

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


let appSettings = getAppSettings()

let dimensions = { widIth: 1500, height: 1000 };

const contextMenu = require('electron-context-menu');
const { options } = require('request')

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
}

function createWindow (specterURL) {  
  if (!mainWindow) {
    initMainWindow()
  }

  // Create the browser window.
  if (appSettings.tor) {
    mainWindow.webContents.session.setProxy({ proxyRules: appSettings.proxyURL });
  }

  updateSpecterdStatus('Specter is running...')

  mainWindow.loadURL(specterURL + '?mode=remote')
  // Open the DevTools.
  // mainWindow.webContents.openDevTools()
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  // Start the tray icon
  logger.info("Framework Ready! Starting tray Icon ...");
  tray = new Tray(path.join(__dirname, 'assets/icon.png'))
  trayMenu = [
    { label: 'Launching Specter...', enabled: false },
    { label: 'Show Specter Desktop',  click() { mainWindow.show() }},
    { label: 'Preferences',  click() { openPreferences() }},
    { label: 'Quit',  click() { quitSpecterd(); app.quit() } },
  ]
  tray.setToolTip('This is my application.')
  tray.setContextMenu(Menu.buildFromTemplate(trayMenu))

  dimensions = screen.getPrimaryDisplay().size;

  // create a new `splash`-Window 
  logger.info("Framework Ready! Initializing Main-Window, popultaing Menu ...");
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
  const specterdPath = specterdDirPath + '/specterd'
  if (fs.existsSync(specterdPath + (platformName == 'win64' ? '.exe' : ''))) {
    getFileHash(specterdPath + (platformName == 'win64' ? '.exe' : ''), function (specterdHash) {
      if (appSettings.specterdHash.toLowerCase() == specterdHash || appSettings.specterdHash == "") {
        
        startSpecterd(specterdPath)
      } else if (appSettings.specterdVersion != "") {
        updatingLoaderMsg('Specterd version could not be validated.<br>Retrying fetching specterd...<br>This might take a minute...')
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

function initMainWindow(specterURL) {
  mainWindow = new BrowserWindow({
    width: parseInt(dimensions.width * 0.8),
    height: parseInt(dimensions.height * 0.8),
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
  updatingLoaderMsg('Fetching the Specter binary...<br>This might take a minute...')
  updateSpecterdStatus('Fetching Specter binary...')
  logger.info("Using version ", appSettings.specterdVersion);
  logger.info(`https://github.com/cryptoadvance/specter-desktop/releases/download/${appSettings.specterdVersion}/specterd-${appSettings.specterdVersion}-${platformName}.zip`);
  download(`https://github.com/cryptoadvance/specter-desktop/releases/download/${appSettings.specterdVersion}/specterd-${appSettings.specterdVersion}-${platformName}.zip`, specterdPath + '.zip', function(errored) {
    if (errored == true) {
      updatingLoaderMsg('Fetching specter binary from the server failed, could not reach the server or the file could not have been found.')
      updateSpecterdStatus('Fetching specterd failed...')
      return
    }

    updatingLoaderMsg('Unpacking files...')

    extract(specterdPath + '.zip', { dir: specterdPath + '-dir' }).then(function () {
      let extraPath = ''
      switch (process.platform) {
        case 'darwin':
          extraPath = 'specterd'
          break
        case 'win32':
          extraPath = 'specterd.exe'
          break
        case 'linux':
          extraPath = 'specterd'
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

function updatingLoaderMsg(msg) {
  if (mainWindow) {
    let code = `
    var launchText = document.getElementById('launch-text');
    if (launchText) {
      launchText.innerHTML = '${msg}';
    }
    `;
    mainWindow.webContents.executeJavaScript(code);
  } 
}

function hasSuccessfullyStarted(logs) {
  return logs.toString().includes('  * Running on http')
  //return logs.toString().includes('Serving Flask app "cryptoadvance.specter.server"')
}

function startSpecterd(specterdPath) {
  if (platformName == 'win64') {
    specterdPath += '.exe'
  }
  let appSettings = getAppSettings()
  let hwiBridgeMode = appSettings.mode == 'hwibridge'
  updatingLoaderMsg('Launching Specter Desktop...')
  updateSpecterdStatus('Launching Specter...')
  let specterdArgs = ["server"]
  specterdArgs.push("--no-filelog")
  if (hwiBridgeMode) specterdArgs.push('--hwibridge')
  if (appSettings.specterdCLIArgs != '') {
    if (specterdArgs == null) {
      specterdArgs = []
    }
    let specterdExtraArgs = appSettings.specterdCLIArgs.split('--')
    specterdExtraArgs = specterdExtraArgs.filter(Boolean)
    specterdExtraArgs.forEach((arg, index) => specterdExtraArgs[index] = '--' + arg.trim())
    
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
  var procStdout = ""
  var procStderr = ""
  specterdProcess.stdout.on('data', (data) => {
    procStdout += data
    logger.info("stdout-"+data.toString())
    if(hasSuccessfullyStarted(data)) {
      logger.info(`App seem to to run ...`);
      if (mainWindow) {
        logger.info(`... creating window ...`);
        createWindow(appSettings.specterURL)
        
      }
    }
  });
  specterdProcess.stderr.on('data', (data) => {
    procStderr += data
    logger.info("stderr-"+data.toString())
    if(hasSuccessfullyStarted(data)) {
      logger.info(`App seem to to run ...`);
      if (mainWindow) {
        logger.info(`... creating window ...`);
        createWindow(appSettings.specterURL)
        
      }
    }
  });

  specterdProcess.on('exit', (code) => {
    logger.error(`specterd exited with code ${code}`);
    showError(`specterd exited with code ${code}. Check the logs in the menu!`)
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


function openNewWindow(htmlContentFile) {
  prefWindow = new BrowserWindow({
    width: 700,
    height: 750,
    autoHideMenuBar: true,
    webPreferences: {
      nodeIntegration: true,
      enableRemoteModule: true,
      
    }
  })
  prefWindow.webContents.on('new-window', function(e, url) {
    e.preventDefault();
    shell.openExternal(url);
  });
  prefWindow.loadURL(`file://${__dirname}/${htmlContentFile}`)
  prefWindow.show()
}


function openPreferences() {
  openNewWindow("settings.html")
}

function openErrorLog() {
  openNewWindow("error_logs.html")
}

function showError(error) {
  updatingLoaderMsg('Specter Desktop encounter an error:<br>' + error.toString())
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
