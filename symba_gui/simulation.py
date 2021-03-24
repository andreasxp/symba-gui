import re
from threading import Thread
from time import sleep
from subprocess import Popen, PIPE, DEVNULL
from PySide2.QtCore import QObject, Signal


class Simulation(QObject):
    """Simulation object that interfaces with an external executable."""
    stepChanged = Signal(int, int)
    """Signal that gets emitted every time round or step changes. Emits round, step."""

    completed = Signal(int)
    """Signal that gets emitted when the process completes. Emits exit code."""

    re_round = re.compile(r"Round (\d+)\/\d+:")
    re_step = re.compile(r"  step +(\d+)\/\d+")
    re_separators = re.compile(r"[\r\n]+")

    def __init__(self, poll_interval=1):
        super().__init__()
        self.poll_interval = poll_interval
        self.process = None

        self.current_round = None
        self.current_step = None

        self.return_code = None

    def start(self, cli_args):
        self.process = Popen(
            cli_args,
            stdout=PIPE,
            stderr=DEVNULL,
            text=True
        )
        Thread(target=self.poll).start()

    def poll(self):
        """Poll the process and process stdout. This function is run automatically in a thread after start()."""
        stdout = ""
        
        while True:
            # Blocking if stdout is not closed and empty. poll() runs in a thread.
            stdout += self.process.stdout.read(10000)
            lines = re.split(self.re_separators, stdout)

            step = None
            round = None

            # re search for the latest step and then for the round this step is in.
            for line in reversed(lines):
                if step is None:
                    match = re.match(self.re_step, line)
                    if match:
                        step = int(match[1]) - 1  # CLI adds 1 to step count so they start from 1, not 0
                else:
                    match = re.match(self.re_round, line)
                    if match:
                        round = int(match[1]) - 1  # CLI adds 1 to round count so they start from 1, not 0
                        break
            
            if round != self.current_round or step != self.current_step:
                self.current_round = round
                self.current_step = step
                self.stepChanged.emit(round, step)
            
            return_code = self.process.poll()
            if return_code is not None:
                # Finish polling
                self.return_code = return_code
                self.completed.emit(return_code)
                return
            
            sleep(self.poll_interval)
