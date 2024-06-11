const { Menu } = require('electron')
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')
const readLastLines = require('read-last-lines')
const isMac = process.platform === 'darwin'

const { versionData, specterAppLogPath } = require('./config.js')
const { logger } = require('./logging.js')

// Use different version-data.jsons

// Should look like this:
// {
//   "version": "v2.0.0-pre32",
//   "sha256": "aa049abf3e75199bad26fbded08ee5911ad48e325b42c43ec195136bd0736785"
// }

function getFileHash(filename, callback) {
  let shasum = crypto.createHash('sha256'),
    // Updating shasum with file content
    s = fs.ReadStream(filename)
  s.on('data', function (data) {
    shasum.update(data)
  })
  // making digest
  s.on('end', function () {
    var hash = shasum.digest('hex')
    callback(hash)
  })
}

function getSpecterAppLogs(callback) {
  readLastLines.read(specterAppLogPath, 700).then(callback)
}

module.exports = {
  getFileHash,
  getSpecterAppLogs,
  versionData,
  isMac,
  isMac,
}
