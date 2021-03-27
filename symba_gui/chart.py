import importlib.util

from PySide2.QtGui import QFont, QFontMetricsF
from PySide2.QtWidgets import (
    QWidget, QDialog, QDialogButtonBox, QLabel, QLineEdit, QTextEdit, QHBoxLayout, QVBoxLayout, QFrame
)


class ChartEditor(QDialog):
    def __init__(self, parent=None, title=None, code=None):
        super().__init__(parent=parent)
        self.setWindowTitle("Chart Editor")

        self.wtitle = QLineEdit(title or "Untitled Chart")
        self.wcode = QTextEdit()
        self.wcode.setText(code or "")
        font = QFont("Inconsolata", 12)
        font.setStretch(110)
        metrics = QFontMetricsF(font)
        self.wcode.setFont(font)
        self.wcode.setTabStopDistance(metrics.horizontalAdvance("a")*4)

        lytitle_container = QHBoxLayout()
        lytitle_container.setContentsMargins(0, 0, 0, 0)

        lytitle_container.addWidget(QLabel("Chart title:"))
        lytitle_container.addWidget(self.wtitle)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.wbutton_save = button_box.button(QDialogButtonBox.Save)
        self.wbutton_cancel = button_box.button(QDialogButtonBox.Cancel)

        self.wbutton_save.clicked.connect(self.accept)
        self.wbutton_cancel.clicked.connect(self.reject)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)

        ly = QVBoxLayout()
        self.setLayout(ly)

        ly.addLayout(lytitle_container)
        ly.addWidget(self.wcode)
        ly.addWidget(line)
        ly.addWidget(button_box)
    
    @property
    def title(self):
        return self.wtitle.text()
    
    @title.setter
    def title(self, text):
        self.wtitle.setText(text)
    
    @property
    def code(self):
        return self.wcode.toPlainText()
    
    @code.setter
    def code(self, text):
        self.wcode.setText(text)


class Chart(QWidget):
    """A user-made chart that loads from a python file."""
    def __init__(self, output_dir, path):
        super().__init__()
        self.output_dir = output_dir
        self.path = path
        self.title = path.stem
        self.wchart = QWidget()  # Initialized later in reload()

        ly = QVBoxLayout()
        self.setLayout(ly)
        ly.addWidget(self.wchart)

        self._editor = None

        self.reload()

    def reload(self, path=None):
        self.path = path or self.path
        
        self.layout().removeWidget(self.wchart)

        # Import the module and call chart() function
        spec = importlib.util.spec_from_file_location(self.title, self.path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.wchart = module.chart(str(self.output_dir))

        self.layout().addWidget(self.wchart)

    def editor(self):
        """Return an editor that is linked to this chart."""
        with open(self.path, "r", encoding="utf-8") as f:
            code = f.read()
        
        if self._editor is None:
            self._editor = ChartEditor(self)

            def done(result):
                if not result:
                    return  # User cancelled

                title = self._editor.title
                code = self._editor.code

                self.path.unlink()
                self.path = self.path.parent / (title + ".py")

                with open(self.path, "w", encoding="utf-8") as f:
                    f.write(code)

                self.reload()
            
            self._editor.finished.connect(done)
        
        self._editor.title = self.title
        self._editor.code = code
        
        return self._editor
