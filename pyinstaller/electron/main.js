// Modules to control application life and create native browser window
const {app, BrowserWindow} = require('electron')
const path = require('path')
let specterdProcess;

function createWindow () {
  // Create the browser window.
  const mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  })

  mainWindow.loadURL('http://localhost:25441')

  // Open the DevTools.
  // mainWindow.webContents.openDevTools()
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
  const specterdPath =
  (!app.isPackaged
    ? './specterd-binaries/specterd-'
    : path.join(process.resourcesPath, '../specterd-binaries/specterd-')) +
    process.platform
  const { spawn } = require('child_process');
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
})

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


// In this file you can include the rest of your app's specific main process
// code. You can also put them in separate files and require them here.
