# source: http://stackoverflow.com/questions/2758159/how-to-embed-a-python-interpreter-in-a-pyqt-widget

import sys
import traceback

from black import out


class stdoutProxy:
    def __init__(self):
        self.text = ""

    def flush(self):
        pass

    def write(self, text):
        self.text += text.rstrip("\n")


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
        sys.stdout = stdoutProxy()
        tmp_stdout = sys.stdout

        if type(self.namespace.get(command)) == type(lambda: None):
            return "'{}' is a function. Type '{}()' to use it in the Python console.".format(
                command, command
            )

        try:
            try:
                # eval is generally considered bad practice. use it wisely!
                result = eval(command, self.namespace, self.namespace)
                if result is not None:
                    tmp_stdout.write(repr(result))
            except SyntaxError:
                # exec is generally considered bad practice. use it wisely!
                exec(command, self.namespace, self.namespace)
        except SystemExit:
            self.close()
        except BaseException:
            traceback_lines = traceback.format_exc().split("\n")
            # Remove traceback mentioning this file, and a linebreak
            for i in (3, 2, 1, -1):
                traceback_lines.pop(i)
            tmp_stdout.write("\n".join(traceback_lines))
        sys.stdout = tmp_stdout
        return tmp_stdout.text
