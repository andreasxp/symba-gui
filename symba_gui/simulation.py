import re
import platform
import subprocess as sp
from threading import Thread
from subprocess import Popen, PIPE, DEVNULL
from PySide2.QtCore import QObject, Signal


class Simulation(QObject):
    """Simulation object that interfaces with an external executable."""
    progessAdvanced = Signal(int)
    """Signal that gets emitted every time progess is made. Emits persentage of completion 0 - 100."""

    completed = Signal(int)
    """Signal that gets emitted when the process completes. Emits exit code."""

    re_progress = re.compile(r"(\d+)%")
    re_separators = re.compile(r"[\r\n]+")

    def __init__(self):
        super().__init__()
        self.process = None

        self.current_progess = None

        self.return_code = None
        self.terminate_flag = False
        """Flag that is set if the simulation was terminated manually."""

    def start(self, cli_args):
        creationflags = 0
        if platform.system() == "Windows":
            creationflags = sp.CREATE_NO_WINDOW

        self.process = Popen(
            cli_args,
            stdout=PIPE,
            stderr=DEVNULL,
            text=True,
            creationflags=creationflags
        )
        Thread(target=self.poll).start()

    def terminate(self):
        """Terminate the process if it's running.
        This function sets self.terminate_flag if the process was running and so was terminated.
        """
        if self.running:
            self.terminate_flag = True
            self.process.terminate()

    @property
    def running(self):
        """Return True if the simulation is currently in progress."""
        return self.process is not None and self.return_code is None

    def poll(self):
        """Poll the process and process stdout. This function is run automatically in a thread after start()."""
        for line in iter(self.process.stdout.readline, ""):
            # Read and process lines while there are lines to read
            match = re.search(self.re_progress, line)

            if match:
                progress = int(match[1])
                if progress != self.current_progess:
                    self.progessAdvanced.emit(progress)
                self.current_progess = progress
        
        return_code = self.process.wait()
        self.return_code = return_code
        self.completed.emit(return_code)
        return
