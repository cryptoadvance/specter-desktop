var execFile = require('child_process').execFile;
var path = require('path');

var absolutePath = path.join(process.cwd(), 'specter_osx');
var server = execFile(absolutePath);

function exitHandler(options, exitCode) {
	server.kill('SIGINT');
}

//do something when app is closing
process.on('exit', exitHandler.bind(null,{cleanup:true}));

//catches ctrl+c event
process.on('SIGINT', exitHandler.bind(null, {exit:true}));

// catches "kill pid" (for example: nodemon restart)
process.on('SIGUSR1', exitHandler.bind(null, {exit:true}));
process.on('SIGUSR2', exitHandler.bind(null, {exit:true}));

//catches uncaught exceptions
process.on('uncaughtException', exitHandler.bind(null, {exit:true}));

nw.Window.open('index.html', { width:1200, height:800 }, function(win) {});
