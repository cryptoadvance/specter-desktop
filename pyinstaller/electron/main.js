// Modules to control application life and create native browser window
const {app, BrowserWindow} = require('electron')
const path = require('path')
const fs = require('fs')
const request = require('request')
const extract = require('extract-zip')

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
  // Create the browser window.
  mainWindow.loadURL('http://localhost:25441')

  // Open the DevTools.
  // mainWindow.webContents.openDevTools()
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  // create a new `splash`-Window 
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  })
  
  mainWindow.loadURL(`file://${__dirname}/splash.html`);
  mainWindow.webContents.openDevTools()
  const specterdDirPath = path.resolve(require('os').homedir(), '.specter/specterd-binaries')
  if (!fs.existsSync(specterdDirPath)){
      fs.mkdirSync(specterdDirPath, { recursive: true });
  }
  const specterdPath = specterdDirPath + '/specterd-' + process.platform
  if (fs.existsSync(specterdPath)) {
    startSpecterd(specterdPath)
    return
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
      startSpecterd(specterdPath)
    })
  })
})

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
    createWindow()
  
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
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  if (specterdProcess) {
    specterdProcess.kill('SIGINT')
  }
});
