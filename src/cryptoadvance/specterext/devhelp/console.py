# source: http://stackoverflow.com/questions/2758159/how-to-embed-a-python-interpreter-in-a-pyqt-widget

import traceback
import logging

logger = logging.getLogger(__name__)


class Console:
    def __init__(self):
        self.namespace = {}
        self.updateNamespace({"run": self.run_script})

    def run_script(self, filename):
        with open(filename) as f:
            script = f.read()
        return self.exec_command(script)

    def updateNamespace(self, namespace):
        self.namespace.update(namespace)
        # adding help message with the available keys
        self.namespace.update(
            {
                "help": f"You can try calling any of the following objects: {list(self.namespace.keys())}\n"
                f"Use a trailing '.' to get available methods and propeties, e.g. try: '{list(self.namespace.keys())[-1]}.'\n"
                "The command 'run' can execute python scripts, e.g., run('myscript.py')"
            }
        )

    def exec_command(self, command):
        if callable(self.namespace.get(command)):
            return "'{}' is a function. Type '{}()' to use it in the Python console.".format(
                command, command
            )

        try:
            try:
                # eval is generally considered bad practice. use it wisely!
                logger.info(f'Executing console command "{command}"')
                if command.endswith("."):
                    return {
                        "vars": eval(
                            f"vars({command[:-1]})", self.namespace, self.namespace
                        ),
                        "dir": eval(
                            f"dir({command[:-1]})", self.namespace, self.namespace
                        ),
                    }
                return eval(command, self.namespace, self.namespace)
            except SyntaxError:
                # exec is generally considered bad practice. use it wisely!
                return exec(command, self.namespace, self.namespace)
        except BaseException:
            traceback_lines = traceback.format_exc().split("\n")
            # Remove traceback mentioning this file, and a linebreak
            for i in (3, 2, 1, -1):
                traceback_lines.pop(i)
            return "\n".join(traceback_lines)
