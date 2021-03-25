from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import QLabel, QAbstractButton


class PushLabel(QLabel):
    clicked = Signal()

    def __init__(self, text, parent=None, f=Qt.WindowFlags()):
        super().__init__(text, parent, f)
        self.setTextFormat(Qt.RichText)
        self._true_text = None
        self.setText(text)

        self.linkActivated.connect(lambda: self.clicked.emit())

    def setText(self, text):
        self._true_text = text
        super().setText(f"<a href=\"dummy\">{text}</a>")
    
    def text(self):
        return self._true_text
