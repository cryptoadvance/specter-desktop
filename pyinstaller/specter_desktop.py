from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, \
    QDialog, QDialogButtonBox, QVBoxLayout, QRadioButton, QLineEdit
from PyQt5.QtCore import QRunnable, QThreadPool, QSettings
import sys
import os
import subprocess
import webbrowser
import json
from cryptoadvance.specter.cli import DATA_FOLDER
from cryptoadvance.specter.helpers import deep_update

running = True
path = os.path.dirname(os.path.abspath(__file__))
is_specterd_running = False
specterd_thread = None
settings = QSettings('cryptoadvance', 'specter')
wait_for_specterd_process = None


class SpecterPreferencesDialog(QDialog):
    global settings

    def __init__(self, *args, **kwargs):
        super(SpecterPreferencesDialog, self).__init__(*args, **kwargs)

        self.setWindowTitle("Specter Preferences")
        self.layout = QVBoxLayout()

        QBtn = QDialogButtonBox.Save | QDialogButtonBox.Cancel

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        # Mode setting
        self.mode_local = QRadioButton("Run Local Specter Server")
        self.mode_local.toggled.connect(self.toggle_mode)

        self.mode_remote = QRadioButton("Use a Remote Specter Server")
        self.mode_remote.toggled.connect(self.toggle_mode)

        self.specter_url = QLineEdit(
            placeholderText="Please enter the remote Specter URL"
        )

        is_remote_mode = settings.value(
            'remote_mode',
            defaultValue=False,
            type=bool
        )
        if is_remote_mode:
            self.mode_remote.setChecked(True)
        else:
            self.mode_local.setChecked(True)
            self.specter_url.hide()

        settings.setValue('remote_mode_temp', is_remote_mode)
        remote_specter_url = settings.value(
            'specter_url',
            defaultValue='',
            type=str
        ) if is_remote_mode else ''
        settings.setValue('specter_url_temp', remote_specter_url)
        self.specter_url.setText(remote_specter_url)
        self.specter_url.textChanged.connect(
            lambda: settings.setValue(
                'specter_url_temp',
                self.specter_url.text()
            )
        )

        self.layout.addWidget(self.mode_local)
        self.layout.addWidget(self.mode_remote)
        self.layout.addWidget(self.specter_url)

        self.layout.addWidget(self.buttonBox)
        self.resize(500, 180)
        self.setLayout(self.layout)

    def toggle_mode(self):
        if self.mode_local.isChecked():
            settings.setValue('remote_mode_temp', False)
            self.specter_url.hide()
        else:
            settings.setValue('remote_mode_temp', True)
            self.specter_url.show()


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
    global specterd_thread, running
    start_specterd_menu = menu.actions()[0]
    start_specterd_menu.setEnabled(False)
    start_specterd_menu.setText('Starting up Specter{} daemon...'.format(
                ' HWIBridge' if settings.value(
                    "remote_mode", defaultValue=False, type=bool
                ) else ''
            ))
    while running:
        line = specterd_thread.stdout.readline()
        if b'Serving Flask app' in line:
            print("* Started Specter daemon...")
            start_specterd_menu.setText('Specter{} daemon is running'.format(
                ' HWIBridge' if settings.value(
                    "remote_mode", defaultValue=False, type=bool
                ) else ''
            ))
            toggle_specterd_status(menu)
            open_specter_window()
            return
        elif b'Failed' in line or b'Error' in line:
            start_specterd_menu.setText('Start Specter daemon'.format(
                ' HWIBridge' if settings.value(
                    "remote_mode", defaultValue=False, type=bool
                ) else ''
            ))
            start_specterd_menu.setEnabled(True)
            return


def run_specterd(menu):
    global specterd_thread, wait_for_specterd_process
    try:
        specterd_command = [os.path.join(sys._MEIPASS, 'specterd/{}'.format(
            'hwibridge' if settings.value(
                "remote_mode", defaultValue=False, type=bool
            ) else 'specterd'
        ))]
        specterd_thread = subprocess.Popen(
            specterd_command,
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
    global settings
    webbrowser.open(settings.value("specter_url", type=str), new=1)


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
        start_specterd_menu.setText('Start Specter{} daemon'.format(
                ' HWIBridge' if settings.value(
                    "remote_mode", defaultValue=False, type=bool
                ) else ''
            ))
        start_specterd_menu.setEnabled(True)
        stop_specterd_menu.setEnabled(False)
        open_specter_menu.setEnabled(False)
    is_specterd_running = not is_specterd_running


def quit_specter(app):
    global running
    running = False
    if specterd_thread:
        specterd_thread.terminate()
    app.quit()


def open_settings():
    global settings
    dlg = SpecterPreferencesDialog()
    if dlg.exec_():
        is_remote_mode = settings.value(
            'remote_mode_temp',
            defaultValue=False,
            type=bool
        )
        settings.setValue(
            'remote_mode',
            is_remote_mode
        )

        specter_url_temp = settings.value(
            'specter_url_temp',
            defaultValue='http://localhost:25441/',
            type=str
        )

        settings.setValue(
            'specter_url',
            specter_url_temp if is_remote_mode else 'http://localhost:25441/'
        )
        # TODO: Add PORT setting


def init_desktop_app():
    global settings
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
    start_specterd_menu = QAction("Start Specter{} daemon".format(
                ' HWIBridge' if settings.value(
                    "remote_mode", defaultValue=False, type=bool
                ) else ''
            ))
    stop_specterd_menu = QAction("Stop Specter daemon")
    open_specter_menu = QAction("Open Specter")

    start_specterd_menu.triggered.connect(lambda: run_specterd(menu))
    menu.addAction(start_specterd_menu)

    stop_specterd_menu.triggered.connect(lambda: stop_specterd(menu))
    menu.addAction(stop_specterd_menu)

    open_specter_menu.triggered.connect(open_specter_window)
    menu.addAction(open_specter_menu)

    toggle_specterd_status(menu)

    open_settings_menu = QAction("Preferences")
    open_settings_menu.triggered.connect(open_settings)
    menu.addAction(open_settings_menu)

    # Add a Quit option to the menu.
    quit = QAction("Quit")
    quit.triggered.connect(lambda: quit_specter(app))
    menu.addAction(quit)

    # Add the menu to the tray
    tray.setContextMenu(menu)

    app.setWindowIcon(icon)

    # Setup settings
    if settings.value('first_time', defaultValue=True, type=bool):
        settings.setValue('first_time', False)
        settings.setValue('remote_mode', False)
        settings.setValue('specter_url', 'http://localhost:25441/')
        open_settings()

    run_specterd(menu)

    sys.exit(app.exec_())


if __name__ == "__main__":
    init_desktop_app()
