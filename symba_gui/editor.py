import base64
from PySide2.QtCore import QUrl, QCoreApplication
from PySide2.QtWebEngineWidgets import QWebEngineView
import symba_gui as package


class Editor(QWebEngineView):
    _no_result = object()

    def __init__(self, parent=None):
        super().__init__(parent)

        editor_index = package.dir / "data/monaco-editor-0.23.0/index.html"
        self.load(QUrl.fromLocalFile(str(editor_index)))

    def _run(self, query):
        """Communicate with the internal webpage by running JS and waiting for a result."""
        result = self._no_result
        def callback(query_result):
            nonlocal result
            result = query_result
        
        self.page().runJavaScript(query, 0, callback)

        app = QCoreApplication.instance()
        while result is self._no_result:
            app.processEvents()
        return result

    def text(self):
        return self._run("monaco.editor.getModels()[0].getValue()")

    def setText(self, text):
        text = text.encode()
        text = base64.b64encode(text)
        text = text.decode()
        self._run(f"monaco.editor.getModels()[0].setValue(atob('{text}'))")

    def setLanguage(self, language):
        self._run(f"monaco.editor.setModelLanguage(monaco.editor.getModels()[0],'{language}')")
    