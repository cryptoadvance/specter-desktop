""" Stuff to deal with executing things on the os-level """
import os, sys, subprocess
import logging

logger = logging.getLogger(__name__)


def which(program):
    """mimics the "which" command in bash but even for stuff not on the path.
    Also has implicit pyinstaller support
    Place your executables like --add-binary '.env/bin/hwi:.'
    ... and they will be found.
    returns a full path of the executable and if a full path is passed,
    it will simply return it if found and executable
    will raise an Exception if not found
    """

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    if getattr(sys, "frozen", False):
        # Best understood with the snippet below this section:
        # https://pyinstaller.readthedocs.io/en/v3.3.1/runtime-information.html#using-sys-executable-and-sys-argv-0
        exec_location = os.path.join(sys._MEIPASS, program)
        if is_exe(exec_location):
            logger.debug("Found %s executable in %s" % (program, exec_location))
            return exec_location

    fpath, program_name = os.path.split(program)
    if fpath:
        if is_exe(program):
            logger.debug("Found %s executable in %s" % (program, program))
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                logger.debug("Found %s executable in %s" % (program, path))
                return exe_file
    raise Exception(f"Couldn't find executable {program} cwd={os.getcwd()}")


# should work in all python versions
def run_shell(cmd):
    """
    Runs a shell command.
    Example: run(["ls", "-a"])
    Returns: dict({"code": returncode, "out": stdout, "err": stderr})
    """
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        return {"code": proc.returncode, "out": stdout, "err": stderr}
    except Exception as e:
        return {"code": 0xF00DBABE, "out": b"", "err": e}


def get_last_lines_from_file(file_localtion, x=50):
    """returns an array of the last x lines of a file"""
    with open(file_localtion, "r") as the_file:
        lines = the_file.readlines()
        last_lines = lines[-x:]
    return last_lines
