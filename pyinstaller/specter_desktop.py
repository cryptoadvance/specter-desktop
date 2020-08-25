from PyQt5.QtGui import QIcon, QCursor, QDesktopServices
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, \
    QDialog, QDialogButtonBox, QVBoxLayout, QRadioButton, QLineEdit, \
    QFileDialog, QLabel, QWidget
from PyQt5.QtCore import QRunnable, QThreadPool, QSettings, QUrl, \
    Qt, pyqtSignal, pyqtSlot, QObject, QSize, QPoint
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

import sys
import os
import subprocess
import webbrowser
import json
import platform
from cryptoadvance.specter.config import DATA_FOLDER
from cryptoadvance.specter.helpers import deep_update

running = True
path = os.path.dirname(os.path.abspath(__file__))
is_specterd_running = False
specterd_thread = None
settings = QSettings('cryptoadvance', 'specter')
wait_for_specterd_process = None


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class SpecterPreferencesDialog(QDialog):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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

# Cross communication between threads via signals
# https://www.learnpyqt.com/courses/concurrent-execution/multithreading-pyqt-applications-qthreadpool/

class WorkerSignals(QObject):
    error = pyqtSignal()
    result = pyqtSignal()

class ProcessRunnable(QRunnable):
    def __init__(self, menu):
        QRunnable.__init__(self)
        self.menu = menu
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        menu = self.menu
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
                # open_specter_window()
                self.signals.result.emit()
                return
            elif b'Failed' in line or b'Error' in line:
                start_specterd_menu.setText('Start Specter daemon'.format(
                    ' HWIBridge' if settings.value(
                        "remote_mode", defaultValue=False, type=bool
                    ) else ''
                ))
                start_specterd_menu.setEnabled(True)
                self.signals.error.emit()
                return

    def start(self):
        QThreadPool.globalInstance().start(self)

def run_specterd(menu, view):
    global specterd_thread, wait_for_specterd_process
    try:
        specterd_command = [
            os.path.join(
                resource_path('specterd'),
                '{}{}'.format(
                    'hwibridge' if settings.value(
                        "remote_mode", defaultValue=False, type=bool
                    ) else 'specterd',
                    '.exe' if platform.system() == "Windows" else '')
            )
        ]
        specterd_thread = subprocess.Popen(
            specterd_command,
            stdout=subprocess.PIPE
        )
        wait_for_specterd_process = ProcessRunnable(menu)
        wait_for_specterd_process.signals.result.connect(lambda: open_webview(view))
        wait_for_specterd_process.signals.error.connect(lambda: print("error"))
        wait_for_specterd_process.start()
    except Exception as e:
        print("* Failed to start Specter daemon {}".format(e))


def stop_specterd(menu, view):
    try:
        if specterd_thread:
            specterd_thread.terminate()
        view.close()
    except Exception as e:
        print(e)
    print("* Stopped Specter daemon")
    toggle_specterd_status(menu)


def open_specter_window():
    webbrowser.open(settings.value("specter_url", type=str), new=1)


def toggle_specterd_status(menu):
    global is_specterd_running
    start_specterd_menu = menu.actions()[0]
    stop_specterd_menu = menu.actions()[1]
    open_webview_menu = menu.actions()[2]
    open_browser_menu = menu.actions()[3]

    if is_specterd_running:
        start_specterd_menu.setEnabled(False)
        stop_specterd_menu.setEnabled(True)
        open_webview_menu.setEnabled(True)
        open_browser_menu.setEnabled(True)
    else:
        start_specterd_menu.setText('Start Specter{} daemon'.format(
                ' HWIBridge' if settings.value(
                    "remote_mode", defaultValue=False, type=bool
                ) else ''
            ))
        start_specterd_menu.setEnabled(True)
        stop_specterd_menu.setEnabled(False)
        open_webview_menu.setEnabled(False)
        open_browser_menu.setEnabled(False)
    is_specterd_running = not is_specterd_running


def quit_specter(app):
    global running
    running = False
    if specterd_thread:
        specterd_thread.terminate()
    app.quit()


def open_settings():
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

        hwibridge_settings_path = os.path.join(
            os.path.expanduser(DATA_FOLDER),
            "hwi_bridge_config.json"
        )

        if is_remote_mode:
            config = {
                'whitelisted_domains': 'http://127.0.0.1:25441/'
            }
            if os.path.isfile(hwibridge_settings_path):
                with open(hwibridge_settings_path, "r") as f:
                    file_config = json.loads(f.read())
                    deep_update(config, file_config)
            with open(hwibridge_settings_path, "w") as f:
                if 'whitelisted_domains' in config:
                    whitelisted_domains = ''
                    if specter_url_temp not in config[
                        'whitelisted_domains'
                    ].split():
                        config['whitelisted_domains'] += ' ' + specter_url_temp
                    for url in config['whitelisted_domains'].split():
                        if not url.endswith("/") and url != '*':
                            # make sure the url end with a "/"
                            url += "/"
                        whitelisted_domains += url.strip() + '\n'
                    config['whitelisted_domains'] = whitelisted_domains
                f.write(json.dumps(config, indent=4))
        # TODO: Add PORT setting

class WebEnginePage(QWebEnginePage):
    """Web page"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.featurePermissionRequested.connect(self.onFeaturePermissionRequested)
        self.profile().downloadRequested.connect(self.onDownloadRequest)

    def onFeaturePermissionRequested(self, url, feature):
        """Enable camera and other stuff"""
        # allow everything
        self.setFeaturePermission(url, feature, QWebEnginePage.PermissionGrantedByUser)

    def onDownloadRequest(self, item):
        """Catch dowload files requests"""
        options = QFileDialog.Options()
        path = QFileDialog.getSaveFileName(None,
                        "Where to save?",
                        item.path(),
                        options=options)[0]
        if path:
            item.setPath(path)
            item.accept()

    def createWindow(self, _type):
        """
        Catch clicks on _blank urls
        and open it in default browser
        """
        page = WebEnginePage(self)
        page.urlChanged.connect(self.open_browser)
        return page

    def open_browser(self, url):
        page = self.sender()
        QDesktopServices.openUrl(url)
        page.deleteLater()

def open_webview(view):
    view.load(QUrl(settings.value("specter_url", type=str)))
    view.show()

class WebView(QWebEngineView):
    """Window with the web browser"""
    def __init__(self, tray, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tray = tray
        self.page = WebEnginePage()
        self.setPage(self.page)
        self.resize(settings.value("size", QSize(1200, 900)))
        self.move(settings.value("pos", QPoint(50, 50)))
        self.loadStarted.connect(self.loadStartedHandler)
        self.loadFinished.connect(self.loadFinishedHandler)
        self.urlChanged.connect(self.loadFinishedHandler)
        self.setWindowTitle("Specter Desktop")

    def loadStartedHandler(self):
        """Set waiting cursor when the page is loading"""
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

    def loadFinishedHandler(self, *args, **kwargs):
        """Recover cursor when done"""
        QApplication.restoreOverrideCursor()

    def closeEvent(self, *args, **kwargs):
        """
        Notify about tray app when window is closed
        for the first time.
        Also save geometry of the window.
        """
        settings.setValue("size", self.size())
        settings.setValue("pos", self.pos())

        if settings.value('first_time_close', defaultValue=True, type=bool):
            settings.setValue('first_time_close', False)
            self.tray.showMessage("Specter is still running!",
                                  "Use tray icon to quit or reopen",
                                  self.tray.icon())
        super().closeEvent(*args, **kwargs)

def init_desktop_app():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    # Create the icon
    icon = QIcon(os.path.join(
        resource_path('specterd'),
        'static/img/icon.png'
    ))

    # Create the tray
    tray = QSystemTrayIcon()
    tray.setIcon(icon)
    tray.setVisible(True)

    # Create webview
    view = WebView(tray)

    # Create the menu
    menu = QMenu()
    start_specterd_menu = QAction("Start Specter{} daemon".format(
                ' HWIBridge' if settings.value(
                    "remote_mode", defaultValue=False, type=bool
                ) else ''
            ))
    start_specterd_menu.triggered.connect(lambda: run_specterd(menu, view))
    menu.addAction(start_specterd_menu)

    stop_specterd_menu = QAction("Stop Specter daemon")
    stop_specterd_menu.triggered.connect(lambda: stop_specterd(menu, view))
    menu.addAction(stop_specterd_menu)

    open_webview_menu = QAction("Open Specter App")
    open_webview_menu.triggered.connect(lambda: open_webview(view))
    menu.addAction(open_webview_menu)

    open_specter_menu = QAction("Open in the browser")
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

    run_specterd(menu, view)

    sys.exit(app.exec_())


if __name__ == "__main__":
    init_desktop_app()
