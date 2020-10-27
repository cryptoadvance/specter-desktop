// Modules to control application life and create native browser window
const { app, BrowserWindow, Menu, screen, shell, dialog } = require('electron')
const path = require('path')
const fs = require('fs')
const request = require('request')
const extract = require('extract-zip')
const crypto = require('crypto')
const defaultMenu = require('electron-default-menu');
const { spawn, exec } = require('child_process');
const console = require('console')
const getAppSettings = require('./helpers').getAppSettings
let appSettings = getAppSettings()

let dimensions = { widIth: 1500, height: 1000 };

const download = (uri, filename, callback) => {
    request.head(uri, (err, res, body) => {
        console.log('content-type:', res.headers['content-type'])
        console.log('content-length:', res.headers['content-length'])
        request(uri).pipe(fs.createWriteStream(filename)).on('close', callback)
    })
}

let specterdProcess
let mainWindow
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
    mainWindow = new BrowserWindow({
      width: parseInt(dimensions.width * 0.8),
      height: parseInt(dimensions.height * 0.8),
      webPreferences
    })
  }
  
  mainWindow.webContents.on("did-fail-load", function() {
      mainWindow.loadURL(`file://${__dirname}/splash.html`);
      updatingLoaderMsg(`Failed to load: ${specterURL}<br>Please make sure the URL is entered correctly in the Preferences and try again...`)
  });

  // Create the browser window.
  if (appSettings.tor) {
    mainWindow.webContents.session.setProxy({ proxyRules: appSettings.proxyURL });
  }

  mainWindow.loadURL(specterURL)
  // Open the DevTools.
  // mainWindow.webContents.openDevTools()
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  dimensions = screen.getPrimaryDisplay().size;

  // create a new `splash`-Window 
  mainWindow = new BrowserWindow({
    width: parseInt(dimensions.width * 0.8),
    height: parseInt(dimensions.height * 0.8),
    webPreferences
  })
  setMainMenu();
  
  mainWindow.loadURL(`file://${__dirname}/splash.html`);

  const specterdDirPath = path.resolve(require('os').homedir(), '.specter/specterd-binaries')
  if (!fs.existsSync(specterdDirPath)){
      fs.mkdirSync(specterdDirPath, { recursive: true });
  }
  const specterdPath = specterdDirPath + '/specterd'
  if (fs.existsSync(specterdPath + (platformName == 'win64' ? '.exe' : ''))) {
    getFileHash(specterdPath + (platformName == 'win64' ? '.exe' : ''), function (specterdHash) {
      if (appSettings.specterdHash.toLowerCase() == specterdHash || appSettings.specterdHash == "") {
        startSpecterd(specterdPath)
      } else if (appSettings.specterdVersion != "") {
        updatingLoaderMsg('Specterd version could not be validated.<br>Retrying fetching specterd...')
        downloadSpecterd(specterdPath)
      } else {
        updatingLoaderMsg('Specterd file could not be validated and no version is configured in the settings<br>Please go to Preferences and set version to fetch or add an executable manually...')
      }
    })
  } else {
    if (appSettings.specterdVersion) {
      downloadSpecterd(specterdPath)
    } else {
      updatingLoaderMsg('Specterd was not found and no version is configured in the settings<br>Please go to Preferences and set version to fetch or add an executable manually...')
    }
  }
})

function downloadSpecterd(specterdPath) {
  updatingLoaderMsg('Fetching the Specter binary...')
  console.log("Using version ", appSettings.specterdVersion);
  console.log(`https://github.com/cryptoadvance/specter-desktop/releases/download/${appSettings.specterdVersion}/specterd-${appSettings.specterdVersion}-${platformName}.zip`);
  download(`https://github.com/cryptoadvance/specter-desktop/releases/download/${appSettings.specterdVersion}/specterd-${appSettings.specterdVersion}-${platformName}.zip`, specterdPath + '.zip', function() {
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
          // app.quit()
          // TODO: This should never happen unless the specterd file was swapped on GitHub.
          // Think of what would be the appropriate way to handle this...
        }
      })
    })
  })
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
function updatingLoaderMsg(msg) {
  let code = `
  var launchText = document.getElementById('launch-text');
  launchText.innerHTML = '${msg}';
  `;
  mainWindow.webContents.executeJavaScript(code);
}

function startSpecterd(specterdPath) {
  if (platformName == 'win64') {
    specterdPath += '.exe'
  }
  let appSettings = getAppSettings()
  let hwiBridgeMode = appSettings.mode == 'hwibridge'
  updatingLoaderMsg('Launching Specter Desktop...')
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
  specterdProcess.stdout.on('data', (_) => {
    if (mainWindow) {
      createWindow(appSettings.specterURL)
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
    console.log(`child process exited with code ${code}`);
  });
}

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', function () {
  mainWindow = null
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  mainWindow = null;
  if (platformName == 'win64') {
    exec('taskkill -F -T -PID ' + specterdProcess.pid);
    process.kill(-specterdProcess.pid)
  }


  if (specterdProcess) {
    specterdProcess.kill('SIGINT')
  }
})

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
  let prefWindow = new BrowserWindow({
    width: 700,
    height: 750,
    parent: mainWindow,
    webPreferences: {
      nodeIntegration: true,
      enableRemoteModule: true
    }
  })
  prefWindow.loadURL(`file://${__dirname}/settings.html`)
  prefWindow.show()
}

function showError(error) {
  dialog.showErrorBox('Specter Desktop encounter an error', error.toString())
  updatingLoaderMsg('Specter Desktop encounter an error:<br>' + error.toString())
}

process.on('unhandledRejection', error => {
  showError(error)
})

process.on("uncaughtException", error => {
  showError(error)
})
