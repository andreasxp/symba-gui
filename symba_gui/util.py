import traceback
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
