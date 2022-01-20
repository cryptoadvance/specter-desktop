Sometimes people have issues where they get an endless Pacman animation and the application is not coming up. If you suffer from this, here are some hints on how to deal with that.

# Check The Logs
The logs are usually in the `.specter` subfolder of your homediretory. There, you might find a file called `specter.log` and/or specterApp.log. If you're running Specter as a binary application (in contrast to a pip installation) which most people do that `specterApp.log` is the relevant file for you. This file might contain content which gives a hint on what's wrong. If you can't find anything suspicious, feel free to create a [pastebin](https://pastebin.com/) and ask in the chat for help (with a link to the created pastebin).

# Check Port 25441
Maybe there is another instance (still) running. Check that via opening your brower here: [http://localhost:25441](http://localhost:25441)
If that's the case, the most easy solution is to reboot your computer.

# Check Whether the Binary is Existing
The first thing Specter is doing if you start up the app is downloading the correct specterd from the GitHub-release page and storing that executable in the `Homefolder/.specter/specterd-binaries` subfolder. You should find a file called `specterd`.
If the file is there but you still get the endless Pacman, try one of the following things:
* delete the file so it'll get redownloaded
* download it from the GitHub-release page and place it manually there, especially if you're not properly connected to the internet
* start the specterd manually via the command line
