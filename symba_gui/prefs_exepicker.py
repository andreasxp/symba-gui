from pathlib import Path

from PySide2.QtCore import Qt, QDir
from PySide2.QtWidgets import (
    QMenu, QVBoxLayout, QFileDialog, QDialog, QCheckBox, QMessageBox, QListWidget, QDialogButtonBox, QFrame
)


class PrefsExePicker(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences: Symba Executables")

        self.executables = None
        self.user_choice = None
        self.builtin = None

        self.wpath_list = QListWidget()
        self.wpath_list.setSortingEnabled(True)
        self.wpath_list.setAlternatingRowColors(True)
        self.wpath_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.wpath_list.currentTextChanged.connect(self.currentTextChangedEvent)
        self.wpath_list.customContextMenuRequested.connect(self.actionShowContextMenu)

        self.wis_default = QCheckBox("Make this executable default for new simulations")
        self.wis_default.setEnabled(False)
        self.wis_default.stateChanged.connect(self.checkboxStateChangedEvent)

        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.wbutton_ok = button_box.button(QDialogButtonBox.Save)
        self.wbutton_cancel = button_box.button(QDialogButtonBox.Cancel)

        self.wbutton_ok.clicked.connect(self.accept)
        self.wbutton_cancel.clicked.connect(self.reject)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)

        ly = QVBoxLayout()
        self.setLayout(ly)

        ly.addWidget(self.wpath_list)
        ly.addWidget(self.wis_default)
        ly.addWidget(line)
        ly.addWidget(button_box)
    
    def actionShowContextMenu(self, pos):
        global_pos = self.wpath_list.mapToGlobal(pos)
        item = self.wpath_list.itemAt(pos)

        if item is None:
            menu = QMenu()
            action_add_path = menu.addAction("Add Path...")

            def getPath():
                path = QFileDialog.getOpenFileName(
                    self, "Choose an executable for running the simulation", QDir.homePath(), "Executables (*.exe)"
                )[0]
                self.addPath(path)

            action_add_path.triggered.connect(getPath)

            menu.exec_(global_pos)
        elif item.text() == self.builtin:
            pass
        else:
            menu = QMenu()
            action_add_path = menu.addAction("Delete")
            action_add_path.triggered.connect(lambda: self.removePath(item.text()))

            menu.exec_(global_pos)

    def currentTextChangedEvent(self, text):
        self.wis_default.setChecked(text == self.user_choice)
        self.wis_default.setDisabled(text == self.builtin)

    def checkboxStateChangedEvent(self, checked):
        if checked == (self.user_choice == self.wpath_list.currentItem().text()):
            # Everything as it should be
            return

        if checked:
            self.user_choice = self.wpath_list.currentItem().text()
        else:
            self.user_choice = self.builtin

    def setData(self, executables, user_choice, builtin):
        """Set current data into the dialog."""
        self.executables = [str(path) for path in executables]
        self.user_choice = str(user_choice)
        self.builtin = str(builtin)

        self.original_executables = self.executables
        self.original_user_choice = self.user_choice

        self.wpath_list.clear()
        for path in self.executables:
            self.wpath_list.addItem(path)

    def addPath(self, path):
        if path not in self.executables:
            # No such path yet
            self.executables.append(path)
            self.wpath_list.addItem(path)
        
        item = self.wpath_list.findItems(path, Qt.MatchExactly)[0]
        self.wpath_list.setCurrentItem(item)
    
    def removePath(self, path):
        items = self.wpath_list.findItems(path, Qt.MatchExactly)
        if len(items) == 0:
            return

        item = self.wpath_list.findItems(path, Qt.MatchExactly)[0]
        self.wpath_list.takeItem(self.wpath_list.row(item))
        self.executables.remove(item.text())
        
        if self.user_choice == path:
            self.user_choice = self.builtin

    def data(self):
        return [Path(s) for s in self.executables], Path(self.user_choice)

    def closeEvent(self, event):
        if self.executables != self.original_executables or self.user_choice != self.original_user_choice:
            msg = QMessageBox(self)
            msg.setWindowTitle("Preferences: Symba Executables")
            msg.setText("Save changes to the executable list?")
            msg.setIcon(QMessageBox.Question)
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msg.setDefaultButton(QMessageBox.Cancel)
            ret = msg.exec_()

            if ret == QMessageBox.Save:
                self.accept()
                event.accept()
            elif ret == QMessageBox.Discard:
                self.reject()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
