import sys
import os
import traceback
import json
from subprocess import Popen
from pathlib import Path
from copy import deepcopy
from PySide6.QtCore import Qt, QStandardPaths, QDir
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMenu, QWidget, QLineEdit, QVBoxLayout, QDockWidget, QFormLayout, QGridLayout,
    QFileDialog, QDialog, QCheckBox, QMessageBox, QListWidget, QDialogButtonBox, QFrame, QTextEdit
)
from PySide6.QtSvgWidgets import QSvgWidget

import symba_gui
from .cli import parse_args
from .dpi import inches_to_pixels as px
from .widgets import PathEdit


module_root = Path(symba_gui.__file__).parent


class PrefsExePicker(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences: Symba Executables")

        self._data = {}
        """Data about the executable list. See setData for format."""
        self._original_data = {}

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
                path = QFileDialog.getOpenFileName(self, "Choose an executable for running the simulation", QDir.homePath(), "Executables (*.exe)")[0]
                self.addPath(path)

            action_add_path.triggered.connect(getPath)

            menu.exec_(global_pos)
        elif item.text() == self._data["built-in"]:
            pass
        else:
            menu = QMenu()
            action_add_path = menu.addAction("Delete")
            action_add_path.triggered.connect(lambda: self.removePath(item.text()))

            menu.exec_(global_pos)

    def currentTextChangedEvent(self, text):
        self.wis_default.setChecked(text == self._data["default"])
        self.wis_default.setDisabled(text == self._data["built-in"])

    def checkboxStateChangedEvent(self, checked):
        if checked == (self._data["default"] == self.wpath_list.currentItem().text()):
            # Everything as it should be
            return

        if checked:
            self._data["default"] = self.wpath_list.currentItem().text()
        else:
            self._data["default"] = self._data["built-in"]

    def setData(self, data: dict):
        """Set current data into the dialog.
        Data is loaded from a dict with a predefined format:
        {
            "paths": [
                "C:/Users/User/symba.exe",
                ...
            ],
            "default": "C:/Users/User/symba.exe"
            "built-in": "<install-path>/bin/symba.exe"
        }
        """
        self._data = deepcopy(data)
        self._original_data = deepcopy(data)

        self.wpath_list.clear()
        for path in data["paths"]:
            self.wpath_list.addItem(path)

    def addPath(self, path):
        if path not in self._data["paths"]:
            # No such path yet
            self._data["paths"].append(path)
            self.wpath_list.addItem(path)
        
        item = self.wpath_list.findItems(path, Qt.MatchExactly)[0]
        self.wpath_list.setCurrentItem(item)
    
    def removePath(self, path):
        items = self.wpath_list.findItems(path, Qt.MatchExactly)
        if len(items) == 0:
            return

        item = self.wpath_list.findItems(path, Qt.MatchExactly)[0]
        self.wpath_list.takeItem(self.wpath_list.row(item))
        self._data["paths"].remove(item.text())
        
        if self._data["default"] == path:
            self._data["default"] = self._data["built-in"]

    def data(self):
        return self._data

    def closeEvent(self, event):
        if self._data != self._original_data:
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Exception catching -------------------------------------------------------------------------------------------
        self.__excepthook__ = sys.excepthook
        sys.excepthook = self.excepthook
        
        # Settings -----------------------------------------------------------------------------------------------------
        self.app_data_dir = Path(QStandardPaths.standardLocations(QStandardPaths.AppDataLocation)[0])
        """Directory of user-specific application data."""
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        
        if (self.app_data_dir / "config.json").exists():
            # Load config file
            with open(self.app_data_dir / "config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            # If config file does not exist, create it
            default_executable_path = module_root / "bin/symba.exe"

            self.config = {
                "executables": {
                    "paths": [
                        str(default_executable_path)
                    ],
                    "default": str(default_executable_path),
                    "built-in": str(default_executable_path)
                }
            }

            with open(self.app_data_dir / "config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f)

        # Contents -----------------------------------------------------------------------------------------------------
        w = QWidget()
        ly = QVBoxLayout()
        w.setLayout(ly)
        self.setCentralWidget(w)

        self.wdock_config = QDockWidget("Simulation Properties")
        self.wdock_config.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.wdock_config.visibilityChanged.connect(lambda visible: self.action_view_config.setChecked(visible))
        self.addDockWidget(Qt.LeftDockWidgetArea, self.wdock_config)

        self.wconfig = QWidget()
        self.wdock_config.setWidget(self.wconfig)
        lyconfig = QFormLayout()
        self.wconfig.setLayout(lyconfig)

        self.woutput_dir = PathEdit()
        self.woutput_dir.dialog().setFileMode(QFileDialog.ExistingFile)
        lyconfig.addRow("Output directory:", self.woutput_dir)

        self.wadditional_args = QLineEdit()
        lyconfig.addRow("Additional arguments:", self.wadditional_args)

        self.wfinal_command = QLineEdit("symba --output-dir 'C:/Users/andreasxp/'")
        self.wfinal_command.setReadOnly(True)
        lyconfig.addRow("Final command:", self.wfinal_command)

        self.wsim_placeholder = QWidget()
        self.wsim_placeholder.setMinimumSize(px(8.695), px(6.522))
        wsim_placeholder_svg = QSvgWidget(str(module_root / "assets/sim_placeholder.svg"))
        wsim_placeholder_svg.setFixedSize(wsim_placeholder_svg.renderer().defaultSize())

        lysim_placeholder = QGridLayout()
        lysim_placeholder.setRowStretch(0, 10)
        lysim_placeholder.setRowStretch(2, 15)
        lysim_placeholder.setColumnStretch(0, 1)
        lysim_placeholder.setColumnStretch(2, 1)
        lysim_placeholder.addWidget(wsim_placeholder_svg, 1, 1)
        self.wsim_placeholder.setLayout(lysim_placeholder)
        self.setCentralWidget(self.wsim_placeholder)

        self.wdock_exepicker = QDockWidget("Executable Selection")
        self.wdock_exepicker.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.wdock_exepicker.visibilityChanged.connect(lambda visible: self.action_view_exepicker.setChecked(visible))
        self.wdock_exepicker.hide()
        self.addDockWidget(Qt.LeftDockWidgetArea, self.wdock_exepicker)

        # Menu bar -----------------------------------------------------------------------------------------------------
        menu_bar = self.menuBar()

        menu_file = menu_bar.addMenu("File")
        
        action_new = menu_file.addAction("New Simulation")
        action_new.triggered.connect(self.actionNew)

        action_new_window = menu_file.addAction("New Window")
        action_new_window.triggered.connect(self.actionNewWindow)

        menu_file.addSeparator()
        menu_file.addAction("Open...")
        menu_file.addSeparator()
        menu_file.addAction("Save")
        menu_file.addAction("Save As...")
        menu_file.addSeparator()
        menu_preferences = menu_file.addMenu("Preferences")
        action_prefs_exepicker = menu_preferences.addAction("Symba Executables")
        action_prefs_exepicker.triggered.connect(self.actionShowPrefsExePicker)
        menu_file.addSeparator()
        action_exit = menu_file.addAction("Exit")
        action_exit.triggered.connect(self.actionExit)

        menu_view = menu_bar.addMenu("View")
        self.action_view_config = menu_view.addAction("Simulation Properties")
        self.action_view_config.setCheckable(True)
        self.action_view_config.setChecked(True)
        self.action_view_config.triggered.connect(lambda checked: self.wdock_config.setVisible(checked))
        self.action_view_exepicker = menu_view.addAction("Executable Selection")
        self.action_view_exepicker.setCheckable(True)
        self.action_view_exepicker.setChecked(False)
        self.action_view_exepicker.triggered.connect(lambda checked: self.wdock_exepicker.setVisible(checked))

    def actionNew(self):
        pass

    def actionNewWindow(self):
        """Start a new experiment. Opens a new window.
        
        This process launches a new simulation window by creating a detached process. The way the process is created
        depends on sys.argv[0] (what is the origin of this process).
        """
        pos_x = self.pos().x() + 40
        pos_y = self.pos().y() + 40
        cli_args = ["--window-pos", f"{pos_x},{pos_y}"]

        if sys.argv[0].endswith("__main__.py"):
            # Application launched with python
            Popen(
                [sys.executable, "-m", Path(sys.argv[0]).parent.name] + cli_args,
                cwd=Path(sys.argv[0]).parent.parent
            )
        else:
            # Assume the application was launched using an executable
            Popen([sys.argv[0]] + cli_args)
        
    def actionExit(self):
        self.close()
    
    # Properties =======================================================================================================
    def actionShowPrefsExePicker(self):
        """Show preferences dialog for the execuatable picker."""
        dialog = PrefsExePicker(self)
        dialog.setData(self.config["executables"])

        def finishedEvent(result):
            print(result)
            if result:
                self.config["executables"] = dialog.data()
                print(self.config["executables"])
        dialog.finished.connect(finishedEvent)

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    # Events ===========================================================================================================
    def closeEvent(self, event):
        with open(self.app_data_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent="\t")

        event.accept()

    # Exception handling ===============================================================================================
    def excepthook(self, etype, value, tb):
        message = QMessageBox(self)
        message.setWindowTitle("Critical Error")
        message.setText(
            "An unknown critical error occured. It is recommended to save your work and restart NFB Studio.\n\n"
            "Please inform the developer, describing what you were doing before the error, and attach the text below."
        )
        message.setIcon(message.Icon.Critical)

        exception_field = QTextEdit()
        exception_field.setText("".join(traceback.format_exception(etype, value, tb)))
        exception_field.setReadOnly(True)
        message.layout().addWidget(exception_field, 1, 0, 1, -1)
        message.exec_()

        self.__excepthook__(etype, value, tb)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("symba_gui")
    app.setApplicationDisplayName("Symba Designer")
    args = parse_args()

    main_window = MainWindow()
    if args.window_pos is not None:
        main_window.move(*args.window_pos)

    main_window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
