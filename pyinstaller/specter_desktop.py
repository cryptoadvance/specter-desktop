from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import QRunnable, QThreadPool
import sys
import os
import subprocess
import webbrowser

path = os.path.dirname(os.path.abspath(__file__))
is_specterd_running = False
specterd_thread = None


class ProcessRunnable(QRunnable):
    def __init__(self, target, args):
        QRunnable.__init__(self)
        self.t = target
        self.args = args

    def run(self):
        self.t(*self.args)

    def start(self):
        QThreadPool.globalInstance().start(self)


def wait_for_specterd(menu):
    global specterd_thread
    start_specterd_menu = menu.actions()[0]
    start_specterd_menu.setEnabled(False)
    start_specterd_menu.setText('Starting up Specter daemon...')
    while True:
        line = specterd_thread.stdout.readline()
        if b'Serving Flask app' in line:
            print("* Started Specter daemon...")
            start_specterd_menu.setText('Specter daemon is running')
            toggle_specterd_status(menu)
            break
        elif b'Failed' in line or b'Error' in line:
            start_specterd_menu.setText('Start Specter daemon')
            start_specterd_menu.setEnabled(True)


def run_specterd(menu):
    global specterd_thread
    try:
        specterd_thread = subprocess.Popen(
            [os.path.join(sys._MEIPASS, 'specterd/specterd')],
            stdout=subprocess.PIPE,
            shell=True
        )
        wait_for_specterd_process = ProcessRunnable(
            target=wait_for_specterd,
            args=(menu, )
        )
        wait_for_specterd_process.start()
    except Exception as e:
        print("* Failed to start Specter daemon {}".format(e))


def stop_specterd(menu):
    global specterd_thread
    try:
        if specterd_thread:
            specterd_thread.terminate()
    except Exception as e:
        print(e)
    print("* Stopped Specter daemon")
    toggle_specterd_status(menu)


def open_specter_window():
    webbrowser.open('http://localhost:25441/', new=1)


def toggle_specterd_status(menu):
    global is_specterd_running
    start_specterd_menu = menu.actions()[0]
    stop_specterd_menu = menu.actions()[1]
    open_specter_menu = menu.actions()[2]

    if is_specterd_running:
        start_specterd_menu.setEnabled(False)
        stop_specterd_menu.setEnabled(True)
        open_specter_menu.setEnabled(True)
    else:
        start_specterd_menu.setText('Start Specter daemon')
        start_specterd_menu.setEnabled(True)
        stop_specterd_menu.setEnabled(False)
        open_specter_menu.setEnabled(False)
    is_specterd_running = not is_specterd_running


def quit_specter(app):
    if specterd_thread:
        specterd_thread.terminate()
    app.quit()


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
    quit.triggered.connect(lambda: quit_specter(app))
    menu.addAction(quit)

    # Add the menu to the tray
    tray.setContextMenu(menu)

    app.setWindowIcon(icon)

    sys.exit(app.exec_())


if __name__ == "__main__":
    init_desktop_app()
