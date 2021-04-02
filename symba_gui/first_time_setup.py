import os
import sys
import platform
from threading import Thread
from tarfile import TarFile
from zipfile import ZipFile
from pathlib import Path
import requests
from PySide2.QtCore import Qt, Signal, QStandardPaths
from PySide2.QtWidgets import QDialog, QMessageBox, QLabel, QProgressBar, QVBoxLayout, QFormLayout
from PySide2.QtSvg import QSvgWidget
import symba_gui as package
from .util import ExceptionMessageBox
from .dpi import inches_to_pixels as px


class FirstTimeSetup(QDialog):
    _progress = Signal(int)
    stepCompleted = Signal()

    def __init__(self, parent, bin_dir):
        super().__init__(parent)

        self.exe_url = None  # Initialized later
        self.bin_dir = bin_dir
        """Path to binary executables."""

        self.compressed_bin_path = (
            Path(QStandardPaths.writableLocation(QStandardPaths.TempLocation)) / "symba-gui" / "archive"
        )

        self._step = None
        self.exception = None
        """The exception that is set from steps if a step failed (including failing from other threads)."""

        self.steps = [
            self.stepDownload,
            self.stepUnpack
        ]

        if platform.system() not in ("Windows", "Linux", "Darwin") or platform.machine() not in ("AMD64", "x86_64"):
            werror_prompt = QMessageBox(self)
            werror_prompt.setWindowTitle("Unable to perform first time setup")
            werror_prompt.setText(
                "Symba Designer cannot be installed on your system.\n"
                "Symba simulations currently only support Windows, Linux, or MacOS, with an x64 architecture."
            )
            werror_prompt.setIcon(werror_prompt.Icon.Critical)
            werror_prompt.exec_()
            sys.exit(1)

        self.setWindowTitle("First time setup")
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setFixedWidth(px(3.5))

        wtitle = QLabel("Performing first time setup:")
        self.wprogress_bar = QProgressBar()
        self._progress.connect(self.wprogress_bar.setValue)

        self.icons = []
        for _ in range(len(self.steps)):
            icon = QSvgWidget(str(package.dir / "data/icons/checkmark.svg"))
            icon.setFixedSize(px(0.15), px(0.15))
            policy = icon.sizePolicy()
            policy.setRetainSizeWhenHidden(True)
            icon.setSizePolicy(policy)
            icon.hide()

            self.icons.append(icon)

        lydetails = QFormLayout()
        lydetails.addRow("Downloading binaries", self.icons[lydetails.rowCount()])
        lydetails.addRow("Unpacking binaries", self.icons[lydetails.rowCount()])
        
        QLabel("Downloading Symba executable")

        ly = QVBoxLayout()
        self.setLayout(ly)

        ly.addWidget(wtitle)
        ly.addWidget(self.wprogress_bar)
        ly.addLayout(lydetails)
    
    def exec_(self):
        self.start()
        super().exec_()

    def start(self, step=0):
        self._step = step
        func = self.steps[step]

        def onCompleted():
            if self.exception is not None:
                ExceptionMessageBox(self, self.exception).exec_()
                sys.exit(1)

            self.icons[self._step].show()

            if self._step != len(self.steps)-1:
                self._step += 1
                self.steps[self._step]()
            else:
                self.accept()

        self.stepCompleted.connect(onCompleted)
        func()

    def stepDownload(self):
        self.wprogress_bar.setRange(0, 100)

        system = platform.system().lower()
        if system == "darwin":
            system = "macos"

        if system == "windows":
            ext = "zip"
        else:
            ext = "tar.gz"
        
        self.exe_url = f"https://github.com/andreasxp/symba-releases/releases/download/1.0.0/symba-x64-{system}.{ext}"
        self.compressed_bin_path.parent.mkdir(parents=True, exist_ok=True)

        Thread(target=self._downloadExe).start()
    
    def stepUnpack(self):
        self.wprogress_bar.setRange(0, 0)
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        Thread(target=self._unpackExe).start()
    
    def _downloadExe(self):
        try:
            r = requests.get(self.exe_url, stream=True)
            
            if r.status_code != 200:
                # Manually raise if status code is anything other than 200
                r.raise_for_status()
            
            length = r.headers.get('content-length')
            if length is None:
                # No content length
                with open(self.compressed_bin_path, "wb") as f:
                    for data in r.iter_content(chunk_size=128):
                        f.write(data)
            else:
                length = int(length)
                consumed_length = 0

                with open(self.compressed_bin_path, "wb") as f:
                    for data in r.iter_content(chunk_size=128):
                        consumed_length += len(data)
                        f.write(data)

                        self._progress.emit(int(100 * consumed_length / length))
            
        except Exception as e:
            self.compressed_bin_path.unlink(missing_ok=True)
            self.exception = e
        
        self.stepCompleted.emit()
    
    def _unpackExe(self):
        try:
            if platform.system() == "Windows":
                with ZipFile(self.compressed_bin_path, "r") as zf:
                    zf.extractall(self.bin_dir)
            else:
                uid = os.geteuid()

                with TarFile(self.compressed_bin_path, "r") as tf:
                    tf.extractall(self.bin_dir, numeric_owner=uid)
        except Exception as e:
            self.exception = e

        self.compressed_bin_path.unlink()
        self.stepCompleted.emit()
