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
let appSettings = getAppSettings()

let dimensions = { widIth: 1500, height: 1000 };

const contextMenu = require('electron-context-menu');

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
        console.log('content-type:', res.headers['content-type'])
        console.log('content-length:', res.headers['content-length'])
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

  mainWindow.loadURL(specterURL)
  // Open the DevTools.
  // mainWindow.webContents.openDevTools()
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  // Start the tray icon
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
  initMainWindow()

  setMainMenu();
  
  mainWindow.loadURL(`file://${__dirname}/splash.html`);

  if (!fs.existsSync(specterdDirPath)){
      fs.mkdirSync(specterdDirPath, { recursive: true });
  }

  let versionData = require('./version-data.json')
  if (!appSettings.versionInitialized || appSettings.versionInitialized != versionData.version) {
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
        updatingLoaderMsg('Specterd version could not be validated.<br>Retrying fetching specterd...')
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
  updatingLoaderMsg('Fetching the Specter binary...')
  updateSpecterdStatus('Fetching Specter binary...')
  console.log("Using version ", appSettings.specterdVersion);
  console.log(`https://github.com/cryptoadvance/specter-desktop/releases/download/${appSettings.specterdVersion}/specterd-${appSettings.specterdVersion}-${platformName}.zip`);
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

function startSpecterd(specterdPath) {
  if (platformName == 'win64') {
    specterdPath += '.exe'
  }
  let appSettings = getAppSettings()
  let hwiBridgeMode = appSettings.mode == 'hwibridge'
  updatingLoaderMsg('Launching Specter Desktop...')
  updateSpecterdStatus('Launching Specter...')
  let specterdArgs = hwiBridgeMode ? ['--hwibridge'] : null
  if (appSettings.specterdCLIArgs != '') {
    if (specterdArgs == null) {
      specterdArgs = []
    }
    let specterdExtraArgs = appSettings.specterdCLIArgs.split('--')
    specterdExtraArgs = specterdExtraArgs.filter(Boolean)
    specterdExtraArgs.forEach((arg, index) => specterdExtraArgs[index] = '--' + arg.trim())
    
    specterdArgs = specterdArgs.concat(specterdExtraArgs)
  }
  specterdProcess = spawn(specterdPath, specterdArgs);
  specterdProcess.stdout.on('data', (data) => {
    if(data.toString().includes('Serving Flask app "cryptoadvance.specter.server"')) {
      if (mainWindow) {
        createWindow(appSettings.specterURL)
      }
    }
  });
  specterdProcess.stderr.on('data', function(_) {
    // https://stackoverflow.com/questions/20792427/why-is-my-node-child-process-that-i-created-via-spawn-hanging
    // needed so specterd won't get stuck
  });

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow(appSettings.specterURL)
  })
  // since these are streams, you can pipe them elsewhere
  specterdProcess.on('close', (code) => {
    updateSpecterdStatus('Specter stopped...')
    console.log(`child process exited with code ${code}`);
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
          console.log(`child process exited with code ${code}`);
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
      console.log('Specterd quit warning: ' + e)
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
  } else {
    menu.unshift({
        label: 'Specter',
        submenu: [{
          label: 'Preferences',
          click: openPreferences,
          accelerator: "CmdOrCtrl+,"
        }]
      } 
    );
  }
  
  Menu.setApplicationMenu(Menu.buildFromTemplate(menu));
}

function openPreferences() {
  prefWindow = new BrowserWindow({
    width: 700,
    height: 750,
    webPreferences: {
      nodeIntegration: true,
      enableRemoteModule: true
    }
  })
  prefWindow.webContents.on('new-window', function(e, url) {
    e.preventDefault();
    shell.openExternal(url);
  });
  prefWindow.loadURL(`file://${__dirname}/settings.html`)
  prefWindow.show()
}

function showError(error) {
  console.error('Specter Desktop encounter an error', error.toString())
  updatingLoaderMsg('Specter Desktop encounter an error:<br>' + error.toString())
}

process.on('unhandledRejection', error => {
  showError(error)
})

process.on("uncaughtException", error => {
  showError(error)
})
