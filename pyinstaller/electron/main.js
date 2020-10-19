// Modules to control application life and create native browser window
const { app, BrowserWindow, Menu, screen, shell } = require('electron')
const path = require('path')
const fs = require('fs')
const request = require('request')
const extract = require('extract-zip')
const crypto = require('crypto')
const defaultMenu = require('electron-default-menu');

let dimensions = { widIth: 1500, height: 1000 };

const versionData = require('./version-data.json')
const console = require('console')

const download = (uri, filename, callback) => {
    request.head(uri, (err, res, body) => {
        console.log('content-type:', res.headers['content-type'])
        console.log('content-length:', res.headers['content-length'])
        request(uri).pipe(fs.createWriteStream(filename)).on('close', callback)
    })
}

let specterdProcess
let mainWindow

function createWindow (specterURL) {
  if (!mainWindow) {
    mainWindow = new BrowserWindow({
      width: parseInt(dimensions.width * 0.8),
      height: parseInt(dimensions.height * 0.8),
      webPreferences: {
        preload: path.join(__dirname, 'preload.js')
      }
    })
  }
  // Create the browser window.
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
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  })
  setMainMenu();
  
  mainWindow.loadURL(`file://${__dirname}/splash.html`);
  if (process.platform != 'darwin') {
    const specterdPath = './specterd-binaries/specterd'
    startSpecterd(specterdPath)
    return
  }
  const specterdDirPath = path.resolve(require('os').homedir(), '.specter/specterd-binaries')
  if (!fs.existsSync(specterdDirPath)){
      fs.mkdirSync(specterdDirPath, { recursive: true });
  }
  const specterdPath = specterdDirPath + '/specterd-' + process.platform
  if (fs.existsSync(specterdPath)) {
    getFileHash(specterdPath, function (specterdHash) {
      if (versionData.sha256 === specterdHash) {
        startSpecterd(specterdPath)
      } else {
        updatingLoaderMsg('Specterd version could not be validated.<br>Retrying fetching specterd...')
        downloadSpecterd(specterdPath)
      }
    })
  } else {
    downloadSpecterd(specterdPath)
  }
})

function downloadSpecterd(specterdPath) {
  updatingLoaderMsg('Fetching the Specter binary...')
  download(`https://github.com/cryptoadvance/specter-desktop/releases/download/v${versionData.version}/specterd-v${versionData.version}-osx.zip`, specterdPath + '.zip', function() {
    updatingLoaderMsg('Unpacking files...')

    extract(specterdPath + '.zip', { dir: specterdPath + '-dir' }).then(function () {
      var oldPath = specterdPath + '-dir/dist/specterd'
      var newPath = specterdPath

      fs.renameSync(oldPath, newPath)
      updatingLoaderMsg('Cleaning up...')
      fs.unlinkSync(specterdPath + '.zip')
      fs.rmdirSync(specterdPath + '-dir', { recursive: true });
      getFileHash(specterdPath, function(specterdHash) {
        if (versionData.sha256 === specterdHash) {
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
  let appSettings = getAppSettings()
  let hwiBridgeMode = appSettings.mode == 'hwibridge'
  const { spawn } = require('child_process');
  updatingLoaderMsg('Launching Specter Desktop...')
  specterdProcess = spawn(specterdPath, hwiBridgeMode ? ['--hwibridge'] : null);
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
  if (specterdProcess) {
    specterdProcess.kill('SIGINT')
  }
})

function setMainMenu() {
  const menu = defaultMenu(app, shell);

  // Add custom menu
  menu[0].submenu.splice(1, 0,
      {
        label: 'Preferences',
        click: openPreferences,
        accelerator: "CmdOrCtrl+,"
      }
  );

  // Set application menu
  Menu.setApplicationMenu(Menu.buildFromTemplate(menu));
}

function openPreferences() {
  let prefWindow = new BrowserWindow({
    width: 700,
    height: 500,
    parent: mainWindow,
    webPreferences: {
      nodeIntegration: true,
      enableRemoteModule: true
    }
  })
  prefWindow.loadURL(`file://${__dirname}/settings.html`)
  prefWindow.show()
}

function getAppSettings() {
  let appSettingsPath = path.resolve(require('os').homedir(), '.specter/app_settings.json')

  let defaultSettings = {
    mode: 'specterd',
    specterURL: 'http://localhost:25441'
  }
  try {
    fs.writeFileSync(appSettingsPath, JSON.stringify(defaultSettings), { flag: 'wx' });
  } catch {
      // settings file already exists
  }
  return require(appSettingsPath)
}
