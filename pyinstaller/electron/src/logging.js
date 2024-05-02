const { specterAppLogPath } = require('./config.js')

// Logging
const { transports, format, createLogger } = require('winston')
const combinedLog = new transports.File({ filename: specterAppLogPath })
const winstonOptions = {
  exitOnError: false,
  format: format.combine(
    format.timestamp(),
    format.json(),
    format.printf((info) => {
      return `${info.timestamp} [${info.level}] : ${info.message}`
    })
  ),
  transports: [new transports.Console({ json: false }), combinedLog],
  exceptionHandlers: [combinedLog],
}
const logger = createLogger(winstonOptions)

module.exports = {
    logger: logger,
}