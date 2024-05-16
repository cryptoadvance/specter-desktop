const { app, BrowserWindow } = require('electron')
const { appSettings, platformName } = require('./config')
const {
  showError,
  updateSpecterdStatus,
  updatingLoaderMsg,
  createWindow,
  loadUrl,
  executeJavaScript,
} = require('./uiHelpers')
const { logger } = require('./logging')
const { spawn } = require('child_process')
const { URL } = require('url')

function checkSpecterd(logs, specterdStarted) {
  // There doesn't seem to be another more straightforward way to check whether specterd is running: https://github.com/nodejs/help/issues/1191
  // Setting a timeout to avoid waiting for specterd endlessly
  const timeout = 180000 // 3 minutes
  const now = Date.now()
  const timeElapsed = now - specterdStarted
  if (timeElapsed > timeout) {
    return 'timeout'
  }
  if (logs.toString().includes('Serving Flask app')) {
    return 'running'
  } else {
    return 'not running'
  }
}

let specterIsRunning = false
function startSpecterd(specterdPath, automaticWalletImport = false) {
  if (platformName == 'win64') {
    specterdPath += '.exe'
  }
  let hwiBridgeMode = appSettings.mode == 'hwibridge'
  updatingLoaderMsg('Launching Specter ...', (showSpinner = 'true'))
  updateSpecterdStatus('Launching Specter ...')
  let specterdArgs = ['server']
  specterdArgs.push('--no-filelog')
  if (hwiBridgeMode) specterdArgs.push('--hwibridge')
  if (appSettings.specterdCLIArgs != '') {
    // User has inputed cli arguments in the UI
    let specterdExtraArgs = appSettings.specterdCLIArgs.split(' ')
    specterdExtraArgs.forEach((arg) => {
      // Ensures that whitespaces are not used as cli arguments
      if (arg != '') {
        specterdArgs.push(arg)
      }
    })
  }
  // locale fix (copying from nodejs-env + adding locales)
  const options = {
    env: { ...process.env },
  }
  options.env['LC_ALL'] = 'en_US.utf-8'
  options.env['LANG'] = 'en_US.utf-8'
  options.env['SPECTER_LOGFORMAT'] = 'SPECTERD: %(levelname)s in %(module)s: %(message)s'
  logger.info(`Starting specter: ${specterdPath} ${specterdArgs.join(' ')}`)
  specterdProcess = spawn(specterdPath, specterdArgs, options)
  const specterdStarted = Date.now()

  // We are checking for both, stdout and stderr, to be on the save side.
  specterdProcess.stdout.on('data', (data) => {
    actOnNewLogLine(data.toString(), 'stdout')
  })

  specterdProcess.stderr.on('data', (data) => {
    actOnNewLogLine(data.toString(), 'stderr')
  })

  const actOnNewLogLine = (logLine, origin) => {
    logger.info(`${origin}: ${logLine.replace(/(\r\n|\n|\r)/gm, '')}`)
    const serverdStatus = checkSpecterd(logLine, specterdStarted)
    if (!specterIsRunning) {
      if (serverdStatus === 'running') {
        logger.info(`Specter server seems to run ...`)
        updateSpecterdStatus('Specter is running')
        specterIsRunning = true
        if (automaticWalletImport === true) {
          logger.info('Performing automatic wallet import ...')
          updatingLoaderMsg('Launching wallet importer. This will only work with a node connection.', (showSpinner = true))
          setTimeout(() => {
            importWallet(walletDataFromUrl)
          }, 3000)
        } else {
          logger.info('Normal startup of Specter.')
          createWindow(appSettings.specterURL)
        }
      } else if (serverdStatus === 'timeout') {
        showError('Specter does not seem to start. Check the logs in the menu for more details.')
        updateSpecterdStatus('Specter does not start')
        logger.error('Startup timeout for specterd exceeded')
      } else {
        updatingLoaderMsg('Still waiting for Specter to start ...')
        updateSpecterdStatus('Specter is starting')
      }
    }
  }

  specterdProcess.on('exit', (code) => {
    if (code !== 0) {
      logger.error(`specterd exited with code ${code}`)
      showError(`Specter exited with exit code ${code}. Check the logs in the menu for more details.`)
    }
  })

  specterdProcess.on('error', (err) => {
    logger.error(`Error starting Specter server: ${err}`)
    showError(`Specter failed to start, due to ${err.message}. Check the logs in the menu for more details.`)
  })

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow(appSettings.specterURL)
  })
  // since these are streams, you can pipe them elsewhere
  specterdProcess.on('close', (code) => {
    updateSpecterdStatus('Specter stopped...')
    logger.info(`child process exited with code ${code}`)
  })
}

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

let walletDataFromUrl
// Checking whether the app was opened via a Specter URL and determine whether to perform a specific startup action
app.on('open-url', (_, url) => {
  logger.info('The app was opened via URL, checking the URL to decide whether to do any automatic actions ...')
  // Parse the URL to extract the query parameters
  const specterUrl = new URL(url)
  const searchParams = specterUrl.searchParams
  // Get the query parameter values
  const action = searchParams.get('action')
  const data = searchParams.get('data')
  if (action === 'importWallet' && data !== '') {
    logger.info('Automatic wallet import identified in the URL, setting automaticWalletImport to true.')
    automaticWalletImport = true
    walletDataFromUrl = data
    // Directly import if the app and specterd is already running
    if (specterIsRunning) {
      logger.info('Performing automatic wallet import ...')
      loadURL(`file://${__dirname}/splash.html`)
      updatingLoaderMsg('Launching wallet importer. This will only work with a node connection.', (showSpinner = true))
      setTimeout(() => {
        importWallet(walletDataFromUrl)
      }, 3000)
    }
  }
})

// Automatically import the wallet json string, bring user to the final import wallet screen.
// Only proceed with the import if the importFromWalletSoftwareBtn can be found.
// If it is not, users are redirected by specterd to the configure connection screen.
function importWallet(walletData) {
  loadUrl(appSettings.specterURL + '/wallets/new_wallet/')
  let code = `
        const importFromWalletSoftwareBtn = document.getElementById('import-from-wallet-software-btn')
        if (importFromWalletSoftwareBtn) {
            importFromWalletSoftwareBtn.click()
            const walletDataTextArea = document.getElementById('txt')
            if (walletDataTextArea) {
            walletDataTextArea.value =  \`${walletData}\`
            }
            const continueBtn = document.getElementById('continue-with-wallet-import-btn');
            continueBtn.click()
        }
        `
  executeJavaScript(code)
}

module.exports = {
  startSpecterd,
  quitSpecterd,
}
