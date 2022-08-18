# source: http://stackoverflow.com/questions/2758159/how-to-embed-a-python-interpreter-in-a-pyqt-widget

import traceback
import logging

logger = logging.getLogger(__name__)


class Console:
    def __init__(self, parent=None):
        self.history = []
        self.namespace = {}
        self.construct = []

        self.updateNamespace({"run": self.run_script})

    def run_script(self, filename):
        with open(filename) as f:
            script = f.read()

        self.exec_command(script)

    def updateNamespace(self, namespace):
        self.namespace.update(namespace)

    def run_command(self, command):
        if command:
            self.exec_command(command)

    def exec_command(self, command):
        output = None

        if type(self.namespace.get(command)) == type(lambda: None):
            return "'{}' is a function. Type '{}()' to use it in the Python console.".format(
                command, command
            )

        try:
            # eval is generally considered bad practice. use it wisely!
            logger.info(f'Executing console command "{command}"')
            if command.endswith("."):
                dir_command = f"dir({command[:-1]})"
                return eval(dir_command, self.namespace, self.namespace)
            return eval(command, self.namespace, self.namespace)
        except SystemExit:
            self.close()
        except BaseException:
            traceback_lines = traceback.format_exc().split("\n")
            # Remove traceback mentioning this file, and a linebreak
            for i in (3, 2, 1, -1):
                traceback_lines.pop(i)
            return "\n".join(traceback_lines)
        return output
