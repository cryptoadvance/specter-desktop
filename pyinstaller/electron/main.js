// Modules to control application life and create native browser window
const {app, BrowserWindow} = require('electron')
const path = require('path')
const fs = require('fs')
const request = require('request')
const extract = require('extract-zip')
const electron = require('electron');
let crypto = require('crypto')
let dimensions = { width: 1500, height: 1000 };

const SPECTERD_HASH = {
  darwin: '4a1c59d90d174114d6c9405eb23b12acd2521bc138c18f7e392dec99e04e9dde'
}

const download = (uri, filename, callback) => {
    request.head(uri, (err, res, body) => {
        console.log('content-type:', res.headers['content-type'])
        console.log('content-length:', res.headers['content-length'])
        request(uri).pipe(fs.createWriteStream(filename)).on('close', callback)
    })
}

let specterdProcess
let mainWindow

function createWindow () {
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
  mainWindow.loadURL('http://localhost:25441')
  
  // Open the DevTools.
  // mainWindow.webContents.openDevTools()
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  dimensions = electron.screen.getPrimaryDisplay().size;

  // create a new `splash`-Window 
  mainWindow = new BrowserWindow({
    width: parseInt(dimensions.width * 0.8),
    height: parseInt(dimensions.height * 0.8),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  })
  
  mainWindow.loadURL(`file://${__dirname}/splash.html`);
  const specterdDirPath = path.resolve(require('os').homedir(), '.specter/specterd-binaries')
  if (!fs.existsSync(specterdDirPath)){
      fs.mkdirSync(specterdDirPath, { recursive: true });
  }
  const specterdPath = specterdDirPath + '/specterd-' + process.platform
  if (fs.existsSync(specterdPath)) {
    getFileHash(specterdPath, function (specterdHash) {
      if (SPECTERD_HASH[process.platform] === specterdHash) {
        startSpecterd(specterdPath)
        return
      } else {
        updatingLoaderMsg('Specterd version could not be validated.<br>Retrying fetching specterd...')
      }
    })
  }
  
  updatingLoaderMsg('Fetching the Specter binary...')
  download("https://github.com/cryptoadvance/specter-desktop/releases/download/v0.8.1/specterd-v0.8.1-osx.zip", specterdPath + '.zip', function() {
    updatingLoaderMsg('Unpacking files...')

    extract(specterdPath + '.zip', { dir: specterdPath + '-dir' }).then(function () {
      var oldPath = specterdPath + '-dir/dist/specterd'
      var newPath = specterdPath

      fs.renameSync(oldPath, newPath)
      updatingLoaderMsg('Cleaning up...')
      fs.unlinkSync(specterdPath + '.zip')
      fs.rmdirSync(specterdPath + '-dir', { recursive: true });
      getFileHash(specterdPath, function(specterdHash) {
        if (SPECTERD_HASH[process.platform] === specterdHash) {
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
})

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
  const { spawn } = require('child_process');
  updatingLoaderMsg('Launching Specter Desktop...')
  specterdProcess = spawn(specterdPath, );
  specterdProcess.stdout.on('data', (_) => {
    if (mainWindow) {
      createWindow()
    }
  
    app.on('activate', function () {
      // On macOS it's common to re-create a window in the app when the
      // dock icon is clicked and there are no other windows open.
      if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })
    // data from the standard output is here as buffers
  });
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
});
