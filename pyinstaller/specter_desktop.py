from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
import sys
import os
from threading import Thread
from cryptoadvance.specter.cli import server, DATA_FOLDER
import webbrowser
path = os.path.dirname(os.path.abspath(__file__))


def is_specterd_running():
    pid_file = os.path.expanduser(os.path.join(DATA_FOLDER, "daemon.pid"))
    return os.path.isfile(pid_file)


def run_specterd(menu):
    thread = Thread(target=server, args=(['--no-debug', '--daemon'], ))
    thread.start()
    thread.join()
    print("* Started Specter daemon...")
    toggle_specterd_status(menu)


def stop_specterd(menu):
    thread = Thread(target=server, args=(['--stop'], ))
    thread.start()
    thread.join()
    print("* Stopped Specter daemon")
    toggle_specterd_status(menu)


def open_specter_window():
    webbrowser.open('http://localhost:25441/', new=1)


def toggle_specterd_status(menu):
    start_specterd_menu = menu.actions()[0]
    stop_specterd_menu = menu.actions()[1]
    open_specter_menu = menu.actions()[2]

    if is_specterd_running():
        start_specterd_menu.setEnabled(False)
        stop_specterd_menu.setEnabled(True)
        open_specter_menu.setEnabled(True)
    else:
        start_specterd_menu.setEnabled(True)
        stop_specterd_menu.setEnabled(False)
        open_specter_menu.setEnabled(False)


def init_desktop_app():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    # Create the icon
    icon = QIcon(os.path.join(
        path,
        os.path.join(
            sys._MEIPASS,
            'static/img/icon.png'
        )
    ))

    # Create the tray
    tray = QSystemTrayIcon()
    tray.setIcon(icon)
    tray.setVisible(True)

    # Create the menu
    menu = QMenu()
    start_specterd_menu = QAction("Start Specter daemon")
    stop_specterd_menu = QAction("Stop Specter daemon")
    open_specter_menu = QAction("Open Specter")

    start_specterd_menu.triggered.connect(lambda: run_specterd(menu))
    menu.addAction(start_specterd_menu)

    stop_specterd_menu.triggered.connect(lambda: stop_specterd(menu))
    menu.addAction(stop_specterd_menu)

    open_specter_menu.triggered.connect(open_specter_window)
    menu.addAction(open_specter_menu)

    toggle_specterd_status(menu)

    # Add a Quit option to the menu.
    quit = QAction("Quit")
    quit.triggered.connect(app.quit)
    menu.addAction(quit)

    # Add the menu to the tray
    tray.setContextMenu(menu)

    app.setWindowIcon(icon)

    sys.exit(app.exec_())


if __name__ == "__main__":
    init_desktop_app()
