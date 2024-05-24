const request = require('request')
const fs = require('fs')
const { app, Menu } = require('electron')
const extract = require('extract-zip')
const { getDownloadLocation } = require('../downloadloc.js')
const { appName, appSettings, platformName, appNameLower, versionDataPath } = require('./config.js')
const { isMac, getFileHash } = require('./helpers.js')
const { logger } = require('./logging.js')
const ProgressBar = require('electron-progressbar')
const { updateSpecterdStatus, updatingLoaderMsg, createProgressBar } = require('./uiHelpers.js')
const { startSpecterd } = require('./specterd.js')

let progressBar

// The standard quit item cannot be replaced / modified and it is not triggering the
// before-quit event on MacOS if a child window is open
const dockMenuWithforceQuit = Menu.buildFromTemplate([
  {
    label: 'Force Quit during download',
    click: () => {
      // If the progress bar exists, close it
      if (progressBar) {
        progressBar.close()
      }
      // Quit the app
      app.quit()
    },
  },
])

function downloadSpecterd(specterdPath) {
  updatingLoaderMsg(`Starting download`)
  updateSpecterdStatus(`Downloading the ${appName} binary...`)
  // Some logging
  logger.info('Using version ' + appSettings.specterdVersion)
  logger.info('Using platformName ' + platformName)
  download_location = getDownloadLocation(appSettings.specterdVersion, platformName)
  logger.info('Downloading from ' + download_location)
  download(download_location, specterdPath + '.zip', function (errored) {
    if (errored == true) {
      updatingLoaderMsg(
        `Downloading the ${appNameLower} binary from GitHub failed, could not reach the server or the file wasn't found.`
      )
      updateSpecterdStatus(`Downloading ${appNameLower}d failed...`)
      return
    }
    updatingLoaderMsg('Download completed. Unpacking files...')
    logger.info('Extracting ' + specterdPath)

    extract(specterdPath + '.zip', { dir: specterdPath + '-dir' }).then(function () {
      let extraPath = ''
      switch (process.platform) {
        case 'darwin':
          extraPath = appNameLower + 'd'
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
      fs.unlinkSync(specterdPath + '.zip')
      fs.rmdirSync(specterdPath + '-dir', { recursive: true })
      getFileHash(specterdPath + (platformName == 'win64' ? '.exe' : ''), function (specterdHash) {
        if (appSettings.specterdHash.toLowerCase() === specterdHash || appSettings.specterdHash == '') {
          startSpecterd(specterdPath)
        } else {
          updatingLoaderMsg('Specterd version could not be validated.')
          logger.error(`hash of downloaded file: ${specterdHash}`)
          logger.error(`Expected hash: ${appSettings.specterdHash} from ${versionDataPath}`)
          updateSpecterdStatus('Failed to launch specterd...')
        }
      })
    })
  })
}

// Download function with progress bar
const download = (uri, filename, callback) => {
  // HEAD request first
  request.head(uri, (err, res, body) => {
    if (res.statusCode != 404) {
      let receivedBytes = 0
      const totalBytes = res.headers['content-length']
      logger.info(`Total size to download: ${totalBytes}`)
      progressBar = createProgressBar(totalBytes)
      // Add Force Quit item during download for MacOS dock
      if (isMac) {
        app.dock.setMenu(dockMenuWithforceQuit)
      }

      progressBar.on('completed', () => {
        progressBar.close()
        // Remove the Force Quit dock item again for Mac
        if (isMac) {
          const updatedDockMenu = Menu.buildFromTemplate(
            dockMenuWithforceQuit.items.filter((item) => item.label !== 'Force Quit during download')
          )
          app.dock.setMenu(updatedDockMenu)
        }
      })

      progressBar.on('aborted', () => {
        logger.warn('Download was aborted before it could finish.')
      })
      // Loggin the download progress
      let lastLogTime = 0
      const logInterval = 5000 // log every 5 seconds
      progressBar.on('progress', () => {
        const currentTime = Date.now()
        if (currentTime - lastLogTime >= logInterval) {
          lastLogTime = currentTime
          logger.info(`Download status: ${((receivedBytes / totalBytes) * 100).toFixed(0)}%`)
        }
      })
      // GET request
      request(uri)
        .on('data', (chunk) => {
          receivedBytes += chunk.length
          if (progressBar) {
            progressBar.value = receivedBytes
          }
        })
        .pipe(fs.createWriteStream(filename))
        .on('close', callback)
    }
    // If the download link was not found, call callback (updatingLoaderMsg with error feedback)
    else {
      logger.error(`Error while trying to download specterd: ${err}`)
      try {
        callback(true)
      } catch (error) {
        logger.error(error)
        throw error
      }
    }
  })
}

const destroyProgressbar = () => {
  if (progressBar) {
    // You can only destroy the progress bar if it hadn't been closed before
    if (progressBar.browserWindow) {
      progressBar.destroy()
    }
    progressBar = null
  }
}

module.exports = {
  downloadSpecterd: downloadSpecterd,
  download: download,
  destroyProgressbar,
}
