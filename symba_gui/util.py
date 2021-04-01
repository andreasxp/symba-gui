import traceback
from threading import Thread
import requests
from PySide2.QtCore import Signal, QObject
from PySide2.QtWidgets import QMessageBox, QTextEdit


class ExceptionMessageBox(QMessageBox):
    def __init__(self, parent, exception):
        super().__init__(parent)
        self.exception = exception

        self.setWindowTitle("Critical Error")
        self.setText(
            "An unknown critical error occured. It is recommended to save your work and restart Symba Designer.\n\n"
            "Please inform the developer, describing what you were doing before the error, and attach the text below."
        )
        self.setIcon(self.Icon.Critical)

        exception_field = QTextEdit()
        exception_field.setText("".join(traceback.format_exception(None, exception, exception.__traceback__)))
        exception_field.setReadOnly(True)
        self.layout().addWidget(exception_field, 1, 0, 1, -1)


class Download(QObject):
    advanced = Signal(int)
    """Emitted when the download has advanced, with a percentage value."""
    completed = Signal()
    failed = Signal(object)

    def __init__(self, parent=None, url=None, path=None):
        super().__init__(parent)

        self.url = url
        self.path = path
        self.finished = False
    
    def start(self):
        """Start the download process."""
        if self.url is None or self.path is None:
            raise ValueError("Download url or path is empty")

        Thread(target=self._stream_download).start()

    def _stream_download(self):
        # Add proxies, and leave `stream=True` for file downloads
        try:
            r = requests.get(self.url, stream=True)
            
            if r.status_code != 200:
                # Manually raise if status code is anything other than 200
                r.raise_for_status()
            
            length = r.headers.get('content-length')
            if length is None:
                # No content length
                with open(self.path, "wb") as f:
                    for data in r.iter_content(chunk_size=128):
                        f.write(data)
            else:
                length = int(length)
                consumed_length = 0

                with open(self.path, "wb") as f:
                    for data in r.iter_content(chunk_size=128):
                        consumed_length += len(data)
                        f.write(data)

                        self.advanced.emit(int(100 * consumed_length / length))
            
            self.completed.emit()
        except Exception as e:
            self.path.unlink(missing_ok=True)
            self.failed.emit(e)
        
        self.finished = True
